# Native UI component catalog

| Component | Expected observation value |
| --- | --- |
| `facts-list` | Label/value facts with evidence references |
| `metrics` | Named numeric or textual metrics |
| `timeline` | Dated events or observations |
| `table` | Homogeneous rows and columns |
| `map` | Public coordinates and labels |
| `image-gallery` | Public image URLs with source evidence |
| `score-breakdown` | `ScoreContribution` dimensions |
| `status-list` | Named states and explanations |
| `contact-list` | Reviewed professional contact projections |
| `form` | Bounded schema-backed inputs that create conversational intent |

All components escape content, show an explicit empty state, and consume data
already produced by plugins. A panel selects an `observation_kind`; it cannot
contain HTML, CSS, JavaScript, DOM selectors, secrets, or calculations. Components
unknown to a particular native shell version disable only their panel and report
the incompatibility.
