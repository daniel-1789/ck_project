import time
import json
import random
import sys
from enum import Enum

"""
Some notes on this program. 
- Run this program with --help to see the possible parameters I created.

- I'm using a curr_tick variable to represent ticks of the clock. Alternatively, a second-based epoch
could have been used. Given the way Python allocates memory, this should be fine for decades of ticks.

- I experimented with a mechansism that with every tick of the clock it performs a rebalancing operation,
going through the list of all food on the overflow shelf and seeing if it could be moved back to the 
proper shelf. However, that is not what the instructions said to do so I left the code present for possib;e
future use. It worked well and helped avoid spoilage of food when I experiemented with couriers arriving
later.

- I'm representing the shelves as an array of FoodShelf objects, a class I created in this program. The center
of that class is a dictionary of FoodItems (another class I created), using the id as the key. 

- The couriers who deliver the food are represented by a dictionary of lists. Each key is a tick of the clock
and the value is a list of FoodItems that need to be picked up. The courier will first look for the food on
the proper shel and the overflow shelf. Since the food is stored in a dictionary on the shelves, this is a
series of O(1) operations - an O(1) to get the list of food ready to be picked up, an O(1) to search for
proper food shelf, and an O(1) to search the overflow shelf. A possible bottleneck is the case where there are
a very large number of FoodItems to be picked up, as each will be processed linerarly. That's clearly not
the case in this exercise, but in a production environment would need to be considered - it might be an 
opportunity for some parallelism, though Python tends to be a bit mediocre when dealing with parallel
programming.

- I found the following text a little ambiguous:
"The kitchen pick-up area has multiple shelves to hold cooked orders at different temperatures. Each order should be 
placed on a shelf that matches the order’s temperature. If that shelf is full, an order can be placed on the 
overflow shelf. If the overflow shelf is full, an existing order of your choosing on the overflow should be 
moved to an allowable shelf with room​.​ If no such move is possible, an order from
the overflow shelf should be discarded as waste (and will not be available for a courier pickup)."

Specifically I was a bit unclear as to which order is to be moved to the overflow shelf  - "an order". I 
experimented with moving the least valuable item and with moving the new order on the overflow shelf. Putting
the new order on the overflow shelf seemed the most reasonable option to me so that is what I went with. 
In a "real world" environment, this is certainly an area where I would talk with the stakeholders as to 
what their desire was. As it is, the code would be very easy to modify to change the algorithm.

- The processing of every tick is a bit of a potential bottleneck on a larger scale environment, as for
every item currently on a shelf new calculations need to be made for the new value of the item. One
optimization to consider on a much larger-scale system would be to, upon putting an item on a shelf, doing
a calculation as to when its value will reach 0 and using a dictionary (i.e. hash table) to store lists of
food that expire on certain ticks of the clock. T
"""

curr_tick = 0  # global clock


class FoodItem:
    """
    Class that represents an item of food either on the shelf or being serviced by courier
    """

    def __init__(self, food_dict):
        self.id = food_dict['id']
        self.name = food_dict['name']
        self.temp = food_dict['temp']
        self.shelf_life = food_dict['shelfLife']
        self.decay_rate = food_dict['decayRate']
        self.time_on_shelf = 0
        self.value = 1.0

    def increase_time_on_shelf(self, time_inc, shelf_mult=1):
        """
        Increase the amount of time food is on the shef
        :param time_inc: How many ticks to increase by
        :param shelf_mult: multiplier to increase decay rate - i.e. if on overflow shelf
        :return: value of this food item after it has been decreased due to passage of time
        """
        self.time_on_shelf += time_inc
        self.value = (float(self.shelf_life) - (float(self.decay_rate) * self.time_on_shelf * shelf_mult)) / float(
            self.shelf_life)
        return self.value


class FoodShelf:
    """
    class to represent a shelf of food awaiting pickup
    """

    def __init__(self, shelf_type, shelf_capacity):
        self.shelf_type = shelf_type
        self.shelf_max = shelf_capacity
        self.food_dict = dict()
        self.decay_mult = 1.0 if shelf_type != 'overflow' else 2.0

    def find_cheapest_item(self):
        """
        Simple linear search to find cheapest item - used when deciding what to toss outf.
        Definitely opportunity for optimization should the shelf change from room for double-digits of entries
        to thousands/millions/etc.
        :return: cheapest item's id
        """
        # linear search of the shelf for cheapest item
        if len(self.food_dict) == 0:
            return None
        else:
            cheapest_value = float('inf')
            cheapest_key = None
            for k, v in self.food_dict.items():
                if v.value < cheapest_value:
                    cheapest_key = k
                    cheapest_value = v.value
        return cheapest_key

    def add_food_to_shelf(self, food_item: FoodItem):
        """
        Add a food item to this shelf. If the shelf is full remove the least valuable item.
        :param food_item: food item to add
        :return: None if food added to shelf without bumping anything, otherwise the food that was bumped
        """
        removed_food = None
        if len(self.food_dict) >= self.shelf_max:
            # remove the minimum value item - just a linear search for now
            remove_key = self.find_cheapest_item()
            removed_food = self.food_dict.pop(remove_key)

        k = food_item.id
        self.food_dict[k] = food_item
        return removed_food

    def remove_food_from_shelf(self, food_key):
        """
        Remove food with the given id from the shelf
        :param food_key: id of food to be removed
        :return: The FoodItem removed, None if it could not be found
        """
        removed_food = self.food_dict.pop(food_key, None)
        return removed_food

    def add_ticks(self, ticks_to_add):
        """
        Add ticks to all the food on the shelf, if anything goes bad/spoils, remove it
        :param ticks_to_add:
        :return: nothing
        """
        food_to_remove = []
        for curr_food in self.food_dict.values():
            curr_value = curr_food.increase_time_on_shelf(ticks_to_add, shelf_mult=self.decay_mult)
            if curr_value <= 0.0:
                food_to_remove.append(curr_food.id)
        for curr_food in food_to_remove:
            self.remove_food_from_shelf(curr_food)
            log_action({self.shelf_type: self}, 'Threw out expired {}'.format(curr_food))



def restore_single_item_to_shelf(shelves):
    """
    Simple routine to restore a single item to a shelf. Go through the overflow shelf and the first item
    that's native shelf has room, take it and put it back there. Could be optimized to save the item with
    the most value or some other algorithm but here just going arbitrarily for the first one that can
    be restred.
    :param shelves: Dictionary of shelves - hot, cold, frozen, overflow.
    :return: Nothing
    """
    restored_items = []
    for k, v in shelves['overflow'].food_dict.items():
        proper_shelf = shelves[v.temp]
        if len(proper_shelf.food_dict) < proper_shelf.shelf_max:
            restored_items.append(k)
            proper_shelf.add_food_to_shelf(v)
            break  # only restore one item but we could actually allow it to run through all
    for curr_key in restored_items:  # realistically only going to run once
        shelves['overflow'].food_dict.pop(curr_key)
        log_action(shelves, 'shelf restored {} from overflow'.format(curr_key))


def restore_to_proper_shelf(shelves):
    """
    This function is currently not in use but has been experimented and does work. The idea is at the
    start of every tick, see if the items on the standby shelf can find their way back to the
    proper shelves. Could add some complexity here at a later point if desired to optimize what gets moved
    and to speed things up but with shelves having room in the double digits not needed at this point.

    Not currently calling this as it goes beyond the parameters of the assignment but offered as a potential
    improvement, mimimizing time spent on overflow shelf.

    :param shelves: Dictionary of shelves - hot, cold, frozen, overflow.
    :return: Nothing
    """
    restored_items = []
    for k, v in shelves['overflow'].food_dict.items():
        proper_shelf = shelves[v.temp]
        if len(proper_shelf.food_dict) < proper_shelf.shelf_max:
            restored_items.append(k)
            proper_shelf.add_food_to_shelf(v)
    for curr_key in restored_items:
        shelves['overflow'].food_dict.pop(curr_key)
    log_action(shelves, 'shelf restore')


class NewItemStatus(Enum):
    ok = 0
    no_shelf = 1
    moved_item_to_overflow = 2
    removed_item_for_room = 3
    already_shelved = 4
    restored_from_overflow = 5

def process_new_item(shelves, curr_item: FoodItem):
    """
    Add a new item to the proper shelf, rearrange other items as required
    :param shelves: Dictionary of shelves
    :param curr_item: Item to be added
    :return: NewItemStatus - unless the shelf cannot be found (no_shelf) or the item is already in a shelf
      (already_shelved), item was added. If moved_item_to_overflow, removed_item_for_room, or
      restored_from_overflow, it had to be placed on the overflow shelf. removed_item_for_room indicates
      something on the overflow shelf had to be thrown out. If restored_from_overflow something from the
      overflow shelf was put in its proper shelf to make room for this item.
    """
    rc = NewItemStatus.ok

    #  - Make sure it does not already exist
    for curr_shelf in shelves.values():
        if curr_shelf.food_dict.get(curr_item.id, None) is not None:
            log_action(shelves,
                       'New item {} already on shelf {}.'.format(
                           curr_item.id, curr_shelf.shelf_type
                       ))

            return NewItemStatus.already_shelved

    # make sure the shelf it is to go on actually exists
    proper_shelf = shelves.get(curr_item.temp, None)
    if proper_shelf is None:
        log_action(shelves,
                   'New item {} cannot be added to non-existent shelf {}.'.format(
                       curr_item.id, curr_item.temp
                   ))

        return NewItemStatus.no_shelf

    #  see if can fit into proper shelf without dropping anything
    if len(proper_shelf.food_dict) < proper_shelf.shelf_max:
        # simply add it
        proper_shelf.add_food_to_shelf(curr_item)
        log_action(shelves,'New item {} added.'.format(curr_item.id))
        rc = NewItemStatus.ok
    else:
        # need to add to overflow - text is a little ambiguous - could interpret as
        # moving something already present or putting this new item on overflow
        # putting this item on overflow seems most reasonable
        overflow_shelf = shelves.get('overflow')
        if len(overflow_shelf.food_dict) < overflow_shelf.shelf_max:
            overflow_shelf.add_food_to_shelf(curr_item)
            log_action(shelves, 'New item {} added to overflow.'.format(curr_item.id))
            rc = NewItemStatus.moved_item_to_overflow
        else:
            # see if we can move something to its proper shelf
            restore_single_item_to_shelf(shelves)
            if len(overflow_shelf.food_dict) < overflow_shelf.shelf_max:
                overflow_shelf.add_food_to_shelf(curr_item)
                log_action(shelves, 'New item {} added to overflow, restored other from overflow.'.format(
                            curr_item.id))
                rc = NewItemStatus.restored_from_overflow
            else:
                # worst case - need to remove something. Pick the thing that is cheapest
                removed_item =  overflow_shelf.add_food_to_shelf(curr_item)
                log_action(shelves, 'New item {} added to overflow.  Tossed {}'.format(
                               curr_item.id, removed_item.id))
                rc = NewItemStatus.removed_item_for_room
    return rc


def create_shelves(hot_size, cold_size, frozen_size, overflow_size):
    """
    Simply create the shelves of the indicated sizes
    :param hot_size:
    :param cold_size:
    :param frozen_size:
    :param overflow_size:
    :return:
    """
    hot_shelf = FoodShelf('hot', hot_size)
    cold_shelf = FoodShelf('cold', cold_size)
    frozen_shelf = FoodShelf('frozen', frozen_size)
    overflow_shelf = FoodShelf('overflow', overflow_size)
    shelves = {'hot': hot_shelf, 'cold': cold_shelf, 'frozen': frozen_shelf, 'overflow': overflow_shelf}
    return shelves


def courier_action(shelves, couriers):
    """
    Look in the dictionary of courier times to see if anything needs to be retrieved in this tick
    :param shelves:
    :param couriers:dictionary of couriers - key is the tick they arrive, value is a list of FoodItems to pick up
    :return: List of FoodItems removed from the shelves by the courier
    """
    global curr_tick

    removed_list = []  # list of what is removed from all shelves by the courier arrival

    curr_couriers = couriers.pop(curr_tick, [])
    for courier in curr_couriers:
        # see if on proper shelf first
        removed_food = shelves[courier.temp].remove_food_from_shelf(courier.id)
        if removed_food is None:
            removed_food = shelves['overflow'].remove_food_from_shelf(courier.id)
            if removed_food is None:
                log_action(shelves, 'Courier could not find {}'.format(courier.id))
            else:
                removed_list.append(removed_food)
                log_action(shelves, 'Courier picked up and delivered {} of value {} from overflow'.format(
                    removed_food.id, removed_food.value))
        else:
            log_action(shelves, 'Courier picked up and delivered {} of value {} from {}'.format(
                removed_food.id, removed_food.value, courier.temp))
            removed_list.append(removed_food)
    return removed_list


def log_action(shelves, action_string):
    """
    Simple logger. Could redirect this to a standard logging file if desired but for this exervcise seemed to
    be easiest just to print
    :param shelves:
    :param action_string:
    :return:
    """
    global curr_tick
    print('At time tick {}, {}'.format(curr_tick, action_string))
    if shelves is not None:
        print('Shelves:')
        for shelf in shelves.values():
            print('shelf: {}. Capacity: {}  Currently {}'.format(shelf.shelf_type, shelf.shelf_max,
                                                                 len(shelf.food_dict)))
            for curr_item in shelf.food_dict.values():
                print('id: {}, name: {}, temp: {}, time: {}, value: {}'.format(
                    curr_item.id, curr_item.name, curr_item.temp, curr_item.time_on_shelf, curr_item.value)
                )
            print('---')
    print('==========================================')


def main(time_between_ticks, number_per_tick, json_fn, hot_size, cold_size, frozen_size, overflow_size, courier_low,
         courier_size):
    """
    main routine - takes the parameters parsed from the command line and loops until both the json has been
    completely ingested and all scheduled couriers are done. A courier is created immediately after an item
    is put on a shelf. It is scheduled for a random time in the future. A dictionary of ticks holds lists of
    couriers (just another instance of the FoodItem to be grabbed) - doing it as dictionary allows for quick
    hashing.
    :param time_between_ticks:
    :param number_per_tick:
    :param json_fn:
    :param hot_size:
    :param cold_size:
    :param frozen_size:
    :param overflow_size:
    :param courier_low:
    :param courier_size:
    :return: nothing
    """
    global curr_tick

    total_ingested = 0
    global shelves
    shelves = create_shelves(hot_size, cold_size, frozen_size, overflow_size)
    with open(json_fn, 'r') as target:
        json_list = json.load(target)
    len_list = len(json_list)
    jsons = iter(json_list)
    couriers = dict()  # whenever we schedule a courier, create/update dictionary entry with their arrival time

    while total_ingested < len_list or len(couriers) > 0:
        time.sleep(time_between_ticks)
        curr_tick += 1
        for curr_shelf in shelves.values():
            curr_shelf.add_ticks(1)
        courier_action(shelves, couriers)  # for every tick, see if there's any couriers ready to go.
        # at this point we could trigger a shelf reshuffling to restore things from overflow to proper shelves
        if total_ingested < len_list:
            for i in range(number_per_tick):
                curr_item = next(jsons)
                food_item = FoodItem(curr_item)
                total_ingested += 1
                rc = process_new_item(shelves, food_item)
                if rc != NewItemStatus.no_shelf and rc != NewItemStatus.already_shelved:
                    courier_time = random.randint(courier_low, courier_low + courier_size) + curr_tick
                    courier_slot = couriers.pop(courier_time, [])
                    courier_slot.append(food_item)
                    couriers[courier_time] = courier_slot
                if total_ingested >= len_list:
                    break


def usage_message(help_request = False):
    """
    Simple usage message.
    :return: Exits 1
    """
    print('Usage - all parameters are optional')
    print('--tick <float> time_in_sec_between_ticks')
    print('--num_ingest number_orders_to_ingest_per_tick')
    print('--input json_file_name')
    print('--num_hot hot_shelf_capacity')
    print('--num_cold cold_shelf_capacity')
    print('--num_frozen frozen_shelf_capacity')
    print('--num_overflow overflow_shelf_capacity')
    print('--courier_low min_seconds_delay_for_courier')
    print('--courier_num num_additional_possible_seconds_delay')
    print('--help')
    if not help_request:
        exit(1)


if __name__ == "__main__":
    # setup default values
    fn = 'orders.json'
    tick_time = 1.0
    num_ingest = 2
    hot_size = 10
    cold_size = 10
    frozen_size = 10
    overflow_size = 15
    courier_low = 2
    courier_num = 5
    help_request = False
    try:
        if len(sys.argv) > 1:
            pointer = 1
            while pointer < len(sys.argv):
                curr_arg = sys.argv[pointer]
                pointer += 1
                if curr_arg == '--tick':
                    tick_time = float(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--num_ingest':
                    num_ingest = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--input':
                    fn = sys.argv[pointer]
                    pointer += 1
                elif curr_arg == '--num_hot':
                    hot_size = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--num_cold':
                    cold_size = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--num_frozen':
                    frozen_size = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--num_overflow':
                    overflow_size = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--courier_low':
                    courier_low = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--courier_num':
                    courier_num = int(sys.argv[pointer])
                    pointer += 1
                elif curr_arg == '--help':
                    help_request = True
                    usage_message(help_request=True)
                    break
                else:
                    raise ()
    except:
        usage_message()

    if not help_request:
        main(tick_time, num_ingest, fn, hot_size, cold_size, frozen_size, overflow_size, courier_low, courier_num)
