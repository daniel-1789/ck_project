import time
import json
import random
import sys
from enum import Enum

curr_tick = 0
shelves = []

class FoodItem:
    def __init__(self, food_dict):
        self.id = food_dict['id']
        self.name = food_dict['name']
        self.temp = food_dict['temp']
        self.shelf_life = food_dict['shelfLife']
        self.decay_rate = food_dict['decayRate']
        self.time_on_shelf = 0
        self.value = 1.0

    def increase_time_on_shelf(self, time_inc, shelf_mult=1):
        self.time_on_shelf += time_inc
        self.value = (float(self.shelf_life) - (float(self.decay_rate) * self.time_on_shelf * shelf_mult))/float(self.shelf_life)
        return self.value


class FoodShelf:
    def __init__(self, shelf_type, shelf_capacity):
        self.shelf_type = shelf_type
        self.shelf_max = shelf_capacity
        self.food_dict = dict()
        self.decay_mult = 1.0 if shelf_type != 'overflow' else 2.0

    def find_cheapest_item(self):
        # linear search of the shelf for cheapest item
        if len(self.food_dict) == 0:
            return None
        else:
            cheapest_value = float('inf')
            cheapest_key = None
            for k,v in self.food_dict.items():
                if v.value < cheapest_value:
                    cheapest_key = k
                    cheapest_value = v.value
        return cheapest_key

    def add_food_to_shelf(self, food_item: FoodItem):
        removed_food = None
        if len(self.food_dict) >= self.shelf_max:
            # remove the minimum value item - just a linear search for now
            remove_key = self.find_cheapest_item()
            removed_food = self.food_dict.pop(remove_key)

        k = food_item.id
        self.food_dict[k] = food_item
        return removed_food

    def remove_food_from_shelf(self, food_key):
        removed_food = self.food_dict.pop(food_key, None)
        return removed_food

    def add_ticks(self, ticks_to_add):
        food_to_remove = []
        for curr_food in self.food_dict.values():
            curr_value = curr_food.increase_time_on_shelf(ticks_to_add, shelf_mult=self.decay_mult)
            if curr_value <= 0.0:
                food_to_remove.append(curr_food.id)
        for curr_food in food_to_remove:
            self.remove_food_from_shelf(curr_food)
            log_action({self.shelf_type: self}, 'Threw out expired {}'.format(curr_food))


def do_tick_housekeeping(time_between_ticks):
    time.sleep(time_between_ticks)

def restore_to_proper_shelf(shelves):
    # walk through the overflow shelf and see if items can be put back where they belong. remember don't remove
    # from what we are iterating over
    restored_items = []
    for k,v in shelves['overflow'].food_dict.items():
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
    moved_to_overflow = 2
    moved_from_overflow = 3

def process_new_item(shelves, curr_item: FoodItem):
    rc = 'ok'
    # Step 1 - see if can fit into proper shelf without dropping anything
    proper_shelf = shelves.get(curr_item.temp, None)
    if proper_shelf is None:
        return NewItemStatus.no_shelf

    dropped_item = proper_shelf.add_food_to_shelf(curr_item)

    # step 2 - if we removed something add it to overflow
    if dropped_item is not None:
        lost_item = shelves['overflow'].add_food_to_shelf(dropped_item)
        if lost_item is not None:
            log_action(shelves,
                       'New item {} added. Moved {} to overflow. Tossed {}'.format(
                           curr_item.id, dropped_item.id, lost_item.id))
            rc = NewItemStatus.moved_from_overflow
        else:
            log_action(shelves,
                       'New item {} added. Moved {} to overflow.'.format(
                           curr_item.id, dropped_item.id
                       ))
            rc = NewItemStatus.moved_to_overflow
    else:
        log_action(shelves,
                   'New item {} added.'.format(
                       curr_item.id
                   ))
        rc = NewItemStatus.ok
    return rc


def create_shelves(hot_size, cold_size, frozen_size, overflow_size):
    hot_shelf = FoodShelf('hot', hot_size)
    cold_shelf = FoodShelf('cold', cold_size)
    frozen_shelf = FoodShelf('frozen', frozen_size)
    overflow_shelf = FoodShelf('overflow', overflow_size)
    shelves = {'hot': hot_shelf, 'cold': cold_shelf, 'frozen': frozen_shelf, 'overflow': overflow_shelf}
    return shelves

def courier_action(shelves, couriers):
    global curr_tick
    removed_list = []

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
    print ('==========================================')



def tick_thread( time_between_ticks, number_per_tick, json_fn, hot_size, cold_size, frozen_size, overflow_size, courier_low, courier_size):
    global curr_tick

    total_ingested = 0
    global shelves
    shelves = create_shelves(hot_size, cold_size, frozen_size, overflow_size)
    with open(json_fn, 'r') as target:
        json_list = json.load(target)
    len_list = len(json_list)
    jsons = iter(json_list)
    couriers = dict()

    while total_ingested < len_list or len(couriers) > 0 :
        do_tick_housekeeping(time_between_ticks)
        curr_tick += 1
        for curr_shelf in shelves.values():
            curr_shelf.add_ticks(1)
        courier_action(shelves, couriers)
        restore_to_proper_shelf(shelves)
        if total_ingested < len_list:
            for i in range(number_per_tick):
                curr_item = next(jsons)
                food_item = FoodItem(curr_item)
                total_ingested += 1
                process_new_item(shelves, food_item)
                courier_time = random.randint(courier_low,courier_low+courier_size) + curr_tick
                courier_slot = couriers.get(courier_time, [])
                courier_slot.append(food_item)
                couriers[courier_time] = courier_slot
                if total_ingested >= len_list:
                    break

if __name__ == "__main__":

    print (sys.argv)
    fn = 'orders.json'
    tick_time = 1.0
    num_ingest = 2
    hot_size = 10
    cold_size = 10
    frozen_size = 10
    overflow_size = 15
    courier_low = 2
    courier_num = 5

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

    tick_thread(tick_time, num_ingest,fn, hot_size, cold_size, frozen_size, overflow_size, courier_low, courier_num)

