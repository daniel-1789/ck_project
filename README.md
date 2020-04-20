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
```

## Discussion
### curr_tick

- I'm using a curr_tick variable to represent ticks of the clock. Alternatively, a second-based epoch
could have been used. Given the way Python allocates memory, this should be fine for decades of ticks.

- I experimented with a mechansism that with every tick of the clock it performs a rebalancing operation,
going through the list of all food on the overflow shelf and seeing if it could be moved back to the 
proper shelf. However, that is not what the instructions said to do so I left the code present for possib;e
future use. It worked well and helped avoid spoilage of food when I experiemented with couriers arriving
later.

### Shelves

- I'm representing the shelves as an array of FoodShelf objects, a class I created in this program. The center
of that class is a dictionary of FoodItems (another class I created), using the id as the key. 

### Couriers

- The couriers who deliver the food are represented by a dictionary of lists. Each key is a tick of the clock
and the value is a list of FoodItems that need to be picked up. The courier will first look for the food on
the proper shel and the overflow shelf. Since the food is stored in a dictionary on the shelves, this is a
series of O(1) operations - an O(1) to get the list of food ready to be picked up, an O(1) to search for
proper food shelf, and an O(1) to search the overflow shelf. 

### Pick-up Ambiguity

I found the following text a little ambiguous:
> The kitchen pick-up area has multiple shelves to hold cooked orders at different temperatures. Each order should be 
placed on a shelf that matches the order’s temperature. If that shelf is full, an order can be placed on the 
overflow shelf. If the overflow shelf is full, an existing order of your choosing on the overflow should be 
moved to an allowable shelf with room​.​ If no such move is possible, an order from
the overflow shelf should be discarded as waste (and will not be available for a courier pickup).

Specifically I was a bit unclear as to which order is to be moved to the overflow shelf  - "an order". I 
experimented with moving the least valuable item and with moving the new order on the overflow shelf. Putting
the new order on the overflow shelf seemed the most reasonable option to me so that is what I went with. 
In a "real world" environment, this is certainly an area where I would talk with the stakeholders as to 
what their desire was. As it is, the code would be very easy to modify to change the algorithm.

I did make the moving of items from the overflow shelf - either back to their proper shelf - or to discard -
fairly arbitrary. I did a popitem for disposing of an item on the shelf. I also looked for the first item
on the overflow shelf that could be moved back to its proper shelf.

### Potential Opimizations

- The processing of every tick is a bit of a potential bottleneck on a larger scale environment, as for
every item currently on a shelf new calculations need to be made for the new value of the item. One
optimization to consider on a much larger-scale system would be to, upon putting an item on a shelf, doing
a calculation as to when its value will reach 0 and using a dictionary (i.e. hash table) to store lists of
food that expire on certain ticks of the clock. This would be similar to what was done for the couriers. 
The problem with this approach is every time food is picked up we want to display the shelves, including
the values of the items. O(N) per tick seems a resonable cost to avoid that complexity

- As it stands now, the performance of each tick is O(N), where N is the number of food items on the shelves, which
maxes out at 45. 