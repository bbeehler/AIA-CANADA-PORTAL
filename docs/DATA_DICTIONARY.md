# Data dictionary

## Historical benchmark dataset

The seed dataset is transcribed from *The View from Here: 2015 Productivity Benchmarks in the Canadian Automotive Service Sector*, last updated September 2016. Every record retains a `source_page`.

The portal must always present these values as historical survey benchmarks, not current market estimates.

### Segment observations

| Field | Meaning |
|---|---|
| `segment` | Mechanical repair shop or tire shop with mechanical service |
| `shop_size` | Bay-count band used in the source report |
| `geography_type` | `region` or `national` |
| `geography` | Canadian region or Canada |
| `affiliation` | All shops, with banner, or no banner |
| `sample_size` | Respondents in that cut |
| `average_repair_orders_year` | Mean annual repair order count |
| `average_hours_repair_order` | Mean labour hours sold per repair order |
| `average_repair_orders_technician_day` | Mean repair orders per technician per day |
| `percentage_exceed_two_hours` | Share exceeding two sold hours per repair order |
| `percentage_sales_from_tires` | Share of sales from tires (tire shops only) |
| `percentage_with_apprentices` | Share employing apprentices |
| `hours_sold_technician_day` | Mean sold technician hours per day |
| `percentage_with_service_advisor` | Share employing a service advisor |
| `percentage_parts_from_oem` | Share of parts purchased from OEM channels |
| `source_page` | Printed page in the source report |

### Performance cohorts

The source compares all shops with the top third by ticket size and the top third by technician productivity. The portal labels these as `All shops`, `Ticket size leaders`, and `Productivity leaders`.

## Member shop contribution contract

One row represents an aggregate month for a shop. Direct identifiers are prohibited.

| Field | Type | Rule |
|---|---|---|
| `reporting_month` | `YYYY-MM` | Required |
| `province` | two-letter code | Canadian province or territory |
| `municipality` | text | Optional municipality name; 100 characters maximum |
| `forward_sortation_area` | three characters | Optional first three postal-code characters, such as `K1A`; never a full postal code |
| `shop_type` | text | Mechanical, Tire, Collision, or Other |
| `bay_count` | number | Greater than zero |
| `technician_count` | number | Greater than zero; FTE or consistent headcount methodology |
| `repair_orders` | integer | Non-negative monthly aggregate |
| `hours_sold` | decimal | Non-negative monthly aggregate |
| `labour_sales_cad` | currency | Canadian dollars, before or after tax consistently |
| `parts_sales_cad` | currency | Canadian dollars |
| `tire_sales_cad` | currency | Canadian dollars; zero if not applicable |

Never include customer names, emails, phone numbers, addresses, VINs, licence plates, invoice numbers, work-order numbers, employee names, or free-text customer notes.

Member submissions may contain at most 120 monthly rows. Future reporting months are rejected. Uploads must use only the required columns plus optional `municipality` and `forward_sortation_area`; unexpected columns and spreadsheet formula-like text are rejected. Manual entry builds the same row structure and passes through the same validator. After validation, both contribution paths are stored as normalized CSV files in private Storage and remain unavailable to other members.

## Statistics Canada demographic data

Demographic observations come from the 2021 Census Profile SDMX API. Geography is keyed by the official Dissemination Geography Unique Identifier (DGUID), never by a display name.

| Field | Meaning |
|---|---|
| `geo_uid` | Official 2021 Census DGUID |
| `geo_level` | `province`, `municipality` (CSD), or `postal_region` (FSA) |
| `geo_code` | Province UID, census-subdivision UID, or three-character FSA |
| `province_code` | Two-letter AIA portal province/territory code |
| `metric_code` | Stable AIA portal demographic metric identifier |
| `reference_period` | Census year, income year, or comparison period represented by the value |
| `source_characteristic_id` | Statistics Canada Census Profile characteristic code |
| `source_flow` | `DF_PR`, `DF_CSD`, or `DF_FSA` |
| `retrieved_at` | UTC timestamp of the API synchronization |

The first metric catalogue covers population and growth, density, households, broad age groups, total and after-tax household income, and labour-force rates. Income observations refer to 2020; after-tax income is spending-capacity context and must not be described as current spending. FSA data represents census forward sortation areas derived from reported postal codes, not exact delivery boundaries.

## Linked market scenario

Scenario exports identify every row as `Statistics Canada 2021`, `AIA 2015`, `User assumption`, or `Calculated scenario`. Estimated vehicles, annual auto care pool, pool per serving shop and target-share revenue are calculated planning lenses; they are not stored source observations and must not be described as forecasts.

## Resource CMS

| Field | Meaning |
|---|---|
| `delivery_type` | `internal` for an article rendered in the portal or `external` for a link opened on another website |
| `content_format` | `markdown` or sanitized `html`; applies to internal articles |
| `content` | Internal article body; blank for external links |
| `external_url` | Complete HTTPS destination; blank for internal articles |
| `status` | `draft`, `published`, or `archived`; only published resources are member-visible |

HTML articles allow headings, paragraphs, emphasis, lists, blockquotes, code, tables and HTTPS/mail links. The application strips executable tags and attributes before saving and sanitizes the stored content again before display.

## Governed administrator datasets

Every staged administrator dataset records a `dataset_type`:

| Value | Contract |
|---|---|
| `mixed` | Existing legacy dataset containing both supported benchmark structures |
| `segment` | Regional, national, shop-size and affiliation benchmark rows |
| `performance` | Shop-type, cohort and metric-code performance rows |

The segment contract uses the columns documented under **Historical benchmark dataset → Segment observations**. The performance contract requires `shop_type`, `cohort`, `metric_code`, `metric_label`, `value`, `unit`, `sort_order`, and `source_page`. Supported units are `count`, `hours`, `percent`, `ratio`, `cad`, `days`, and `years`.

Validation requires exact headers and rejects empty files, more than 10,000 rows, unsupported categories or units, negative metrics, percentages outside 0–100, non-integer counts/order/page values, duplicate natural keys, malformed metric codes and spreadsheet formula-like text. `source_page` may be blank but generates a provenance warning.
