# T-ASE manuscript, revision 1

Revised draft of "Who Backs Up? Benchmarking Decentralized Multi-Robot Yield Negotiation in Narrow
Corridors", written in response to the referee review. `../paper_tase/` holds the version that was
reviewed; `../paper_tase/reviews/response_letter.md` is the point-by-point response.

- `main.tex`: main paper (14 pages)
- `supplement.tex`: supplementary material (notation, parameters, extended RQ1/RQ3/RQ4 results,
  Gazebo per-condition table, Bland–Altman plot, reproduction commands)

Build (supplement and main are independent):

```
latexmk -pdf main.tex
latexmk -pdf supplement.tex
```
