import time
import json
import random
import sys
from enum import Enum

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
        Simple linear search to find cheapest item - used when deciding what to toss out/move to a new shelf.
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
        Add a food item to this shelf. If the shelf is full bump the least valuable item
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


def restore_to_proper_shelf(shelves):
    """
    At the start of every tick, see if the items on the standby shelf can find their way back to the
    proper shelves. Could add some complexity here at a later point if desired to optimize what gets moved
    and to speed things up but with shelves having room in the double digits not needed at this point.
    :param shelves: Dictionary of shelves - hot, cold, frozen, standby.
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


def restore_single_item_to_shelf(shelves):
    """
    Simplpe routine to restore a single item to a shelf
    :return: Nothing
    """
    restored_items = []
    for k, v in shelves['overflow'].food_dict.items():
        proper_shelf = shelves[v.temp]
        if len(proper_shelf.food_dict) < proper_shelf.shelf_max:
            restored_items.append(k)
            proper_shelf.add_food_to_shelf(v)
            break  # only restore one item
    for curr_key in restored_items:
        shelves['overflow'].food_dict.pop(curr_key)
        log_action(shelves, 'shelf restored {} from overflow'.format(curr_key))



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
      (already_shelved), item was added. Possible warnings/ informationals include if
      other items had to be moved to overflow - and possibly if something else was moved from it and
      tossed out
    """
    rc = NewItemStatus.ok

    # Step 1 - Make sure it does not already exist
    for curr_shelf in shelves.values():
        if curr_shelf.food_dict.get(curr_item.id, None) is not None:
            log_action(shelves,
                       'New item {} already on shelf {}.'.format(
                           curr_item.id, curr_shelf.shelf_type
                       ))

            return NewItemStatus.already_shelved

    # Step 2 - see if can fit into proper shelf without dropping anything
    proper_shelf = shelves.get(curr_item.temp, None)
    if proper_shelf is None:
        log_action(shelves,
                   'New item {} cannot be added to non-existent shelf {}.'.format(
                       curr_item.id, curr_item.temp
                   ))

        return NewItemStatus.no_shelf

    dropped_item = proper_shelf.add_food_to_shelf(curr_item)

    # Step 3 - if we removed something add it to overflow
    if dropped_item is not None:
        lost_item = shelves['overflow'].add_food_to_shelf(dropped_item)
        if lost_item is not None:
            log_action(shelves,
                       'New item {} added. Moved {} to overflow. Tossed {}'.format(
                           curr_item.id, dropped_item.id, lost_item.id))
            rc = NewItemStatus.removed_item_for_room
        else:
            log_action(shelves,
                       'New item {} added. Moved {} to overflow.'.format(
                           curr_item.id, dropped_item.id
                       ))
            rc = NewItemStatus.moved_item_to_overflow
    else:
        log_action(shelves,
                   'New item {} added.'.format(
                       curr_item.id
                   ))
        rc = NewItemStatus.ok
    return rc

def process_new_item_2(shelves, curr_item: FoodItem):
    """
    Add a new item to the proper shelf, rearrange other items as required
    :param shelves: Dictionary of shelves
    :param curr_item: Item to be added
    :return: NewItemStatus - unless the shelf cannot be found (no_shelf) or the item is already in a shelf
      (already_shelved), item was added. Possible warnings/ informationals include if
      other items had to be moved to overflow - and possibly if something else was moved from it and
      tossed out
    """
    rc = NewItemStatus.ok

    # Step 1 - Make sure it does not already exist
    for curr_shelf in shelves.values():
        if curr_shelf.food_dict.get(curr_item.id, None) is not None:
            log_action(shelves,
                       'New item {} already on shelf {}.'.format(
                           curr_item.id, curr_shelf.shelf_type
                       ))

            return NewItemStatus.already_shelved

    # Step 2 - see if can fit into proper shelf without dropping anything
    proper_shelf = shelves.get(curr_item.temp, None)
    if proper_shelf is None:
        log_action(shelves,
                   'New item {} cannot be added to non-existent shelf {}.'.format(
                       curr_item.id, curr_item.temp
                   ))

        return NewItemStatus.no_shelf

    if len(proper_shelf.food_dict) < proper_shelf.shelf_max:
        # simply add it
        proper_shelf.add_food_to_shelf(curr_item)
        log_action(shelves,
                   'New item {} added.'.format(
                       curr_item.id
                   ))
        rc = NewItemStatus.ok
    else:
        # need to add to overflow - text is a little ambiguous - could interpret as
        # moving something already present or putting this new item on overflow
        # putting this item on overflow seems most reasonable
        overflow_shelf = shelves.get('overflow')
        if len(overflow_shelf.food_dict) < overflow_shelf.shelf_max:
            overflow_shelf.add_food_to_shelf(curr_item)
            log_action(shelves,
                       'New item {} added to overflow.'.format(
                           curr_item.id
                       ))
            rc = NewItemStatus.moved_item_to_overflow
        else:
            # see if we can move something to its proper shelf
            restore_single_item_to_shelf(shelves)
            if len(overflow_shelf.food_dict) < overflow_shelf.shelf_max:
                overflow_shelf.add_food_to_shelf(curr_item)
                log_action(shelves,
                           'New item {} added to overflow, restored other from overflow.'.format(
                               curr_item.id
                           ))
                rc = NewItemStatus.restored_from_overflow
            else:
                # worst case - need to remove something. Pick the thing that is cheapest
                removed_item =  overflow_shelf.add_food_to_shelf(curr_item)
                log_action(shelves,
                           'New item {} added to overflow.  Tossed {}'.format(
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
                log_action(shelves, 'Courier picked up and delivered {} from overflow'.format(removed_food.id))
        else:
            log_action(shelves, 'Courier picked up and delivered {} from {}'.format(removed_food.id, courier.temp))
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
        courier_action(shelves, couriers)
        # restore_to_proper_shelf(shelves)
        if total_ingested < len_list:
            for i in range(number_per_tick):
                curr_item = next(jsons)
                food_item = FoodItem(curr_item)
                total_ingested += 1
                rc = process_new_item_2(shelves, food_item)
                if rc != NewItemStatus.no_shelf and rc != NewItemStatus.already_shelved:
                    courier_time = random.randint(courier_low, courier_low + courier_size) + curr_tick
                    courier_slot = couriers.pop(courier_time, [])
                    courier_slot.append(food_item)
                    couriers[courier_time] = courier_slot
                if total_ingested >= len_list:
                    break


def usage_message():
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

    try:
        if len(sys.argv) > 1:
            pointer = 1
            while pointer < len(sys.argv):
                curr_arg = sys.argv[pointer]
                print(curr_arg)
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
                    raise ()
                else:
                    raise ()
    except:
        usage_message()

    main(tick_time, num_ingest, fn, hot_size, cold_size, frozen_size, overflow_size, courier_low, courier_num)
