# Initial GitHub Issue Backlog

## Project setup
1. Initialize repo, branch protections, and labels
2. Add Python tooling and formatter choices
3. Finalize local config pattern

## Docs
4. Review and finalize Version 1 blueprint
5. Review and finalize packet template
6. Review and finalize journal schema
7. Add architecture diagram

## Data and universe
8. Create canonical S&P 100 universe file
9. Decide initial market-data source for MVP
10. Build daily OHLCV ingestion pipeline

## Features and ranking
11. Define first-pass pullback-in-trend screening rules
12. Implement relative-strength features
13. Implement trend-state features
14. Implement pullback-quality features
15. Implement packet-worthiness threshold logic

## Packet generation
16. Build quick-brief packet template renderer
17. Build deeper-analysis section renderer
18. Add earnings/event-risk labeling block
19. Add position-size guidance block

## Journal and storage
20. Implement SQLite journal schema
21. Add write path for every recommendation
22. Add read path for historical recommendations
23. Add review write path for Ryan-executed trades

## Emailing
24. Set up assistant email account and credentials flow
25. Implement morning watchlist email sender
26. Implement action packet email sender
27. Implement end-of-day recap email sender

## Shadow ledger
28. Implement shadow-trade model
29. Connect paper-broker adapter
30. Compute shadow P&L and excursion metrics
31. Tag earnings-adjacent trades separately

## Evaluation
32. Build weekly scorecard output
33. Build bootcamp KPI report
34. Add postmortem generation for closed trades

## Future, not MVP
35. Add intraday mode after MVP gates are cleared
36. Explore approval-gated live execution after bootcamp success
37. Explore fine-tuning or learned ranking after journal maturity
