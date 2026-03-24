"""Fine-tuning orchestrator with Unsloth and auto-rollback."""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.config import load_config
from src.training.versioning import (
    get_active_model_version,
    get_model_history,
    get_new_examples_since,
    get_performance_by_version,
    get_training_example_counts,
    init_training_tables,
    register_model_version,
    rollback_model,
)

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

TRAIN_SCRIPT = '''# training_data/train.py
# Auto-generated fine-tuning script for Halcyon Lab
# Runs on RTX 3060 12GB using Unsloth + QLoRA

import json
import sys

def main():
    # Install check
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        print("ERROR: Unsloth not installed. Run: pip install unsloth")
        sys.exit(1)

    # Load base model
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen3-8B",
        max_seq_length=2048,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # Load dataset
    from datasets import Dataset
    examples = []
    with open("training_data/dataset.jsonl", "r") as f:
        for line in f:
            examples.append(json.loads(line))

    # Format for chat template
    def format_example(example):
        return {
            "text": tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": example["instruction"]},
                    {"role": "user", "content": example["input"]},
                    {"role": "assistant", "content": example["output"]},
                ],
                tokenize=False,
            )
        }

    dataset = Dataset.from_list(examples).map(format_example)

    # Train
    from trl import SFTTrainer
    from transformers import TrainingArguments

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=TrainingArguments(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=16,
            num_train_epochs=1,
            learning_rate=2e-4,
            fp16=True,
            logging_steps=10,
            output_dir="training_data/checkpoints",
            report_to="none",
        ),
    )
    trainer.train()

    # Save and export to GGUF
    model.save_pretrained("training_data/lora_adapter")
    tokenizer.save_pretrained("training_data/lora_adapter")

    # Merge and export to GGUF Q5_K_M
    model.save_pretrained_gguf(
        "training_data/halcyon-latest",
        tokenizer,
        quantization_method="q5_k_m",
    )
    print("TRAINING COMPLETE: training_data/halcyon-latest-Q5_K_M.gguf")

if __name__ == "__main__":
    main()
'''


def should_train(db_path: str = "ai_research_desk.sqlite3") -> tuple[bool, str]:
    """Check if fine-tuning should be triggered.

    Returns (should_train, reason_string).
    """
    config = load_config()
    training_cfg = config.get("training", {})
    if not training_cfg.get("enabled", False):
        return False, "Training disabled in config"

    threshold = training_cfg.get("auto_train_threshold", 50)
    time_days = training_cfg.get("auto_train_time_days", 7)
    min_examples = training_cfg.get("auto_train_min_examples", 20)

    init_training_tables(db_path)
    active = get_active_model_version(db_path)

    if active:
        since_date = active["created_at"]
        new_count = get_new_examples_since(since_date, db_path)
        created = datetime.fromisoformat(active["created_at"])
        days_since = (datetime.now(ET) - created.replace(tzinfo=ET if created.tzinfo is None else created.tzinfo)).days
    else:
        # No model yet — count all examples
        counts = get_training_example_counts(db_path)
        new_count = counts["total"]
        days_since = 999  # Arbitrary large number

    if new_count >= threshold:
        return True, f"{new_count} new examples since last train (threshold: {threshold})"

    if days_since >= time_days and new_count >= min_examples:
        return True, f"{days_since} days since last train, {new_count} new examples"

    return False, f"{new_count} new examples, {days_since} days since last train (need {threshold} examples or {time_days} days with {min_examples}+ examples)"


def export_training_data(
    output_dir: str = "training_data",
    db_path: str = "ai_research_desk.sqlite3",
) -> tuple[str, int]:
    """Export all training examples to JSONL.

    Returns (file_path, example_count).
    """
    init_training_tables(db_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    file_path = str(Path(output_dir) / "dataset.jsonl")

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT instruction, input_text, output_text FROM training_examples ORDER BY created_at"
        ).fetchall()

    with open(file_path, "w") as f:
        for row in rows:
            f.write(json.dumps({
                "instruction": row["instruction"],
                "input": row["input_text"],
                "output": row["output_text"],
            }) + "\n")

    return file_path, len(rows)


def run_fine_tune(db_path: str = "ai_research_desk.sqlite3") -> dict | None:
    """Run the full fine-tuning pipeline.

    Returns the new model version record on success, or None on failure.
    """
    # Step 1: Export training data
    file_path, example_count = export_training_data(db_path=db_path)
    if example_count == 0:
        print("[TRAINING] No training examples to fine-tune on.")
        return None

    print(f"[TRAINING] Exported {example_count} examples to {file_path}")

    # Step 2: Write training script
    script_path = Path("training_data") / "train.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w") as f:
        f.write(TRAIN_SCRIPT)

    print("[TRAINING] Running fine-tuning script...")

    # Step 3: Run as subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout
        )
    except subprocess.TimeoutExpired:
        print("[TRAINING] ERROR: Fine-tuning timed out after 2 hours")
        return None
    except Exception as e:
        print(f"[TRAINING] ERROR: Failed to run training script: {e}")
        return None

    if result.returncode != 0:
        print(f"[TRAINING] ERROR: Training script failed:")
        print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        return None

    print(result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout)

    # Step 4: Find GGUF and register in Ollama
    gguf_path = _find_gguf("training_data")
    if not gguf_path:
        print("[TRAINING] ERROR: Could not find GGUF file after training")
        return None

    # Write Ollama Modelfile
    modelfile_path = Path("training_data") / "Modelfile"
    with open(modelfile_path, "w") as f:
        f.write(f"FROM ./{gguf_path}\n")

    # Create model in Ollama
    try:
        subprocess.run(
            ["ollama", "create", "halcyon-latest", "-f", str(modelfile_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[TRAINING] ERROR: Failed to register model in Ollama: {e}")
        return None

    # Step 5: Determine version name and register
    history = get_model_history(db_path)
    version_num = len(history) + 1
    version_name = f"halcyon-v{version_num}"

    counts = get_training_example_counts(db_path)

    version_id = register_model_version(
        version_name=version_name,
        examples_count=example_count,
        synthetic_count=counts.get("synthetic_claude", 0),
        outcome_count=counts.get("outcome_win", 0) + counts.get("outcome_loss", 0),
        model_file_path=str(gguf_path),
        db_path=db_path,
    )

    print(f"[TRAINING] Fine-tune complete. Registered {version_name} ({example_count} examples)")

    return {
        "version_id": version_id,
        "version_name": version_name,
        "examples_count": example_count,
    }


def _find_gguf(directory: str) -> str | None:
    """Find GGUF file in directory."""
    for p in Path(directory).rglob("*.gguf"):
        return str(p)
    return None


def check_model_performance(db_path: str = "ai_research_desk.sqlite3") -> dict:
    """Check if the active model is performing well vs previous version.

    Returns action dict with 'action' key: 'rolled_back', 'waiting', or 'none'.
    """
    config = load_config()
    training_cfg = config.get("training", {})
    expectancy_threshold = training_cfg.get("auto_rollback_expectancy_drop", 0.20)
    winrate_threshold = training_cfg.get("auto_rollback_winrate_drop", 0.10)

    perf = get_performance_by_version(db_path)
    if len(perf) < 2:
        # Need at least 2 versions to compare
        active = get_active_model_version(db_path)
        if active:
            current_perf = next((p for p in perf if p["version_name"] == active["version_name"]), None)
            if current_perf and current_perf["trade_count"] < 10:
                return {"action": "waiting", "trades_needed": 10 - current_perf["trade_count"]}
        return {"action": "waiting", "trades_needed": 10}

    current_version = perf[0]
    previous_version = perf[1]

    if current_version["trade_count"] < 10:
        return {"action": "waiting", "trades_needed": 10 - current_version["trade_count"]}

    # Compare performance
    current_exp = current_version.get("expectancy") or 0
    previous_exp = previous_version.get("expectancy") or 0
    exp_drop = previous_exp - current_exp

    current_wr = current_version.get("win_rate", 0)
    previous_wr = previous_version.get("win_rate", 0)
    wr_drop = (previous_wr - current_wr) / 100  # Convert percentage to decimal

    if exp_drop > expectancy_threshold:
        restored = rollback_model(db_path)
        restored_name = restored["version_name"] if restored else "base"
        print(f"[TRAINING] Auto-rollback: {current_version['version_name']} -> {restored_name} (expectancy dropped ${exp_drop:.2f})")
        return {
            "action": "rolled_back",
            "reason": f"Expectancy dropped ${exp_drop:.2f} (threshold: ${expectancy_threshold:.2f})",
            "restored_version": restored_name,
        }

    if wr_drop > winrate_threshold:
        restored = rollback_model(db_path)
        restored_name = restored["version_name"] if restored else "base"
        print(f"[TRAINING] Auto-rollback: {current_version['version_name']} -> {restored_name} (win rate dropped {wr_drop*100:.1f}%)")
        return {
            "action": "rolled_back",
            "reason": f"Win rate dropped {wr_drop*100:.1f}% (threshold: {winrate_threshold*100:.0f}%)",
            "restored_version": restored_name,
        }

    return {"action": "none", "status": "performing well"}
