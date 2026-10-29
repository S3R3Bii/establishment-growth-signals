# Establishment growth signals

A fixed 25% own-history / 75% other-state pool has held equal-series MAE 3.125 percentage points versus 3.327 for the own-lag baseline, a 6.1% reduction across 934 state-sector series and 3,736 annual cases. The selected model is worse in 428 series and four of nineteen sectors, and slightly worse in 2023. All failures remain in the result tables.

The target is a published expansion-rate proxy: job gains at expanding continuing establishments per 100 DHS-average employees in the whole state-sector cell. It is not worker hires, job vacancies or a demonstrated labor shortage. This is a retrospective revised-data comparison; complete prior-year inputs are idealized and original information vintages remain unverified.

Use the pooled model as a benchmark candidate, with its own-lag alternative and local failure record visible. Show opening and continuer components separately, preserve unavailable cells and verify dated release availability before an operational forecast. Current hiring or staffing decisions require timely vacancy, worker-flow and business evidence.

## All validation weights

| Own weight | MAE | MSE | RMSE | Weighted MAE |
| --- | --- | --- | --- | --- |
| 0 | 1.788843 | 7.159998 | 2.675817 | 1.152882 |
| 1/4 | 1.722490 | 6.887452 | 2.624396 | 1.102038 |
| 1/2 | 1.728513 | 7.341322 | 2.709487 | 1.098912 |
| 3/4 | 1.814480 | 8.521606 | 2.919179 | 1.150813 |
| 1 | 1.967781 | 10.428304 | 3.229288 | 1.245183 |

## Held overall

| Model | MAE | MSE | RMSE | Weighted MAE |
| --- | --- | --- | --- | --- |
| Selected 1/4 | 3.124807 | 21.611910 | 4.648861 | 2.546230 |
| Own lag 1 | 3.327210 | 26.275404 | 5.125954 | 2.667888 |

## Every held year

| Year | Cases | Selected MAE | Baseline MAE | Difference |
| --- | --- | --- | --- | --- |
| 2020 | 934 | 1.621557 | 1.818040 | -0.196483 |
| 2021 | 934 | 1.966621 | 2.198047 | -0.231426 |
| 2022 | 934 | 5.132117 | 5.515111 | -0.382995 |
| 2023 | 934 | 3.778933 | 3.777642 | 0.001291 |

## Fixed size subsets

| Minimum prior denom | Cases | Series | Selected MAE | Baseline MAE | Difference |
| --- | --- | --- | --- | --- | --- |
| 1000 | 3732 | 933 | 3.124485 | 3.325703 | -0.201217 |
| 5000 | 3455 | 867 | 3.082839 | 3.250796 | -0.167956 |
| 25000 | 2559 | 648 | 2.812255 | 2.941076 | -0.128821 |

## Every sector

| Sector | Label | Series | Selected MAE | Baseline MAE | Difference |
| --- | --- | --- | --- | --- | --- |
| 11 | Agriculture/forestry | 31 | 3.200861 | 3.829193 | -0.628331 |
| 21 | Mining/extraction | 39 | 4.862585 | 5.177612 | -0.315026 |
| 22 | Utilities | 50 | 3.101715 | 3.960264 | -0.858550 |
| 23 | Construction | 51 | 1.592864 | 1.709688 | -0.116824 |
| 31-33 | Manufacturing | 50 | 1.959406 | 2.110424 | -0.151019 |
| 42 | Wholesale | 51 | 2.018314 | 2.215880 | -0.197566 |
| 44-45 | Retail | 51 | 1.500814 | 1.671365 | -0.170551 |
| 48-49 | Transport/warehousing | 51 | 3.378581 | 3.359554 | 0.019027 |
| 51 | Information | 51 | 4.046648 | 4.095743 | -0.049094 |
| 52 | Finance/insurance | 51 | 1.834795 | 2.274995 | -0.440199 |
| 53 | Real estate/leasing | 51 | 2.397177 | 2.559551 | -0.162374 |
| 54 | Professional/technical | 51 | 2.500913 | 2.555661 | -0.054748 |
| 55 | Company management | 50 | 4.058407 | 4.996047 | -0.937640 |
| 56 | Admin/support | 51 | 3.783324 | 4.150698 | -0.367374 |
| 61 | Education | 51 | 3.083902 | 3.037646 | 0.046256 |
| 62 | Health/social assistance | 51 | 1.478447 | 1.505938 | -0.027491 |
| 71 | Arts/recreation | 51 | 7.867361 | 7.545962 | 0.321398 |
| 72 | Accommodation/food | 51 | 4.320455 | 4.261589 | 0.058865 |
| 81 | Other services | 51 | 2.818479 | 2.852701 | -0.034222 |

## Five largest local failures

| FIPS | sector | Selected MAE | Baseline MAE | Difference |
| --- | --- | --- | --- |
| 56 / 71 | 4.429363 | 1.535492 | 2.893871 |
| 40 / 71 | 6.027131 | 3.482660 | 2.544471 |
| 32 / 21 | 4.074591 | 1.809710 | 2.264881 |
| 44 / 55 | 3.834174 | 1.754246 | 2.079928 |
| 56 / 21 | 5.873542 | 3.793945 | 2.079597 |

## All composition panels

| Sector | Model cases | Complete | Birth rate | Continuer rate | Nonzero residuals | Max residual jobs |
| --- | --- | --- | --- | --- | --- | --- |
| 11 | 124 | 124 | 5.239501 | 10.259712 | 0 | 0 |
| 21 | 156 | 153 | 4.638375 | 9.651229 | 0 | 0 |
| 22 | 200 | 183 | 2.051356 | 6.290245 | 0 | 0 |
| 23 | 204 | 204 | 4.674487 | 11.475035 | 1 | 1 |
| 31-33 | 200 | 200 | 2.017553 | 7.397835 | 0 | 0 |
| 42 | 204 | 204 | 3.118291 | 8.333612 | 0 | 0 |
| 44-45 | 204 | 204 | 3.326205 | 7.316031 | 0 | 0 |
| 48-49 | 204 | 204 | 5.776571 | 9.895691 | 0 | 0 |
| 51 | 204 | 204 | 4.129926 | 10.355117 | 0 | 0 |
| 52 | 204 | 204 | 4.306965 | 10.103031 | 0 | 0 |
| 53 | 204 | 204 | 6.860276 | 9.871472 | 0 | 0 |
| 54 | 204 | 204 | 4.966372 | 10.855810 | 0 | 0 |
| 55 | 200 | 199 | 2.797059 | 11.351910 | 0 | 0 |
| 56 | 204 | 204 | 4.571542 | 11.735687 | 0 | 0 |
| 61 | 204 | 204 | 2.016931 | 7.108247 | 0 | 0 |
| 62 | 204 | 204 | 3.616274 | 7.865248 | 0 | 0 |
| 71 | 204 | 204 | 5.022153 | 12.357128 | 0 | 0 |
| 72 | 204 | 204 | 6.631142 | 9.832129 | 0 | 0 |
| 81 | 204 | 204 | 4.896385 | 9.058715 | 0 | 0 |

All errors are percentage points except MSE (squared percentage points). Difference is selected minus baseline. Size subsets change the reporting population. Composition excludes 21 unavailable-component cases without changing the model population; one one-job creation residual stays unchanged. Full 934-series and monthly/year source/control evidence remains in results/ and data/. Source flags are never reconstructed.
