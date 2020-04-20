# cloud_kitchen
 
## Purpose
Reads a json file or orders and simulates putting them
on shelves and couriers picking them up.

## Usage
Either run from ide or by invoking via a command line python execution.

All parameters are optional:
```
--tick <float> time_in_sec_between_ticks
--num_ingest number_orders_to_ingest_per_tick
--input json_file_name
--num_hot hot_shelf_capacity
--num_cold cold_shelf_capacity
--num_frozen frozen_shelf_capacity
--num_overflow overflow_shelf_capacity
--courier_low min_seconds_delay_for_courier
--courier_num num_additional_possible_seconds_delay
--help
``