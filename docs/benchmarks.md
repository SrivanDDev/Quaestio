# Benchmark observations

Measured October 7 2026 on Linux x86_64 and Python 3.14.4, using the development virtual
environment. Dataset: 10% ERROR; remaining INFO; repeated message strings. Median of
three parser-plus-analyzer runs, with file generation excluded. Peak Python allocations
measured in a separate tracemalloc pass. This is not RSS or a throughput guarantee.

| Format | Events | Distinct errors | Entries/sec | Peak traced bytes |
| --- | --- | --- | --- | --- |
| text | 10,000 | 100 | 195,029 | 158,365 |
| text | 100,000 | 100 | 200,056 | 158,365 |
| ndjson | 100,000 | 100 | 751,621 | 153,282 |
| text | 100,000 | 10,000 | 192,712 | 885,279 |

Run `python scripts/benchmark.py --entries 100000 --format text` after installation.
Change --format to ndjson or --distinct-errors to 10000 for the other workloads.
Use --entries 10000 for the smaller case. Full reasoning and the ranking comparison
are recorded in [implementation-report.md](implementation-report.md).
