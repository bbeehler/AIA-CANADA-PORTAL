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
| `shop_type` | text | Mechanical, Tire, Collision, or Other |
| `bay_count` | number | Greater than zero |
| `technician_count` | number | Greater than zero; FTE or consistent headcount methodology |
| `repair_orders` | integer | Non-negative monthly aggregate |
| `hours_sold` | decimal | Non-negative monthly aggregate |
| `labour_sales_cad` | currency | Canadian dollars, before or after tax consistently |
| `parts_sales_cad` | currency | Canadian dollars |
| `tire_sales_cad` | currency | Canadian dollars; zero if not applicable |

Never include customer names, emails, phone numbers, addresses, VINs, licence plates, invoice numbers, work-order numbers, employee names, or free-text customer notes.
