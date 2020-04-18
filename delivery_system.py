import pandas as pd
import threading
import time
import ijson
import urllib
import json

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
        self.value = (float(self.shelf_life) - (float() * self.time_on_shelf * shelf_mult))/float(self.shelf_life)
        return self.value


class FoodShelf:
    def __init__(self, shelf_type, shelf_capacity):
        self.shelf_type = shelf_type
        self.shelf_max = shelf_capacity
        self.shelf_curr = 0
        self.food_dict = dict()
        self.decay_mult = 1.0 if shelf_type != 'overflow' else 2.0

    def find_cheapest_item(self):
        # linear search of the shelf for cheapest item
        if self.shelf_curr == 0:
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
        if self.shelf_curr >= self.shelf_max:
            # remove the minimum value item - just a linear search for now
            remove_key = self.find_cheapest_item()
            removed_food = self.food_dict.pop(remove_key)
            self.shelf_curr -= 1

        k = food_item.id
        self.food_dict[k] = food_item
        self.shelf_curr += 1
        return removed_food

    def remove_food_from_shelf(self, food_key):
        removed_food = self.food_dict.pop(food_key, None)
        if removed_food is not None:
            self.shelf_curr -= 1
        return removed_food

    def add_ticks(self, ticks_to_add):
        for curr_food in self.food_dict.items():
            curr_value = curr_food.increase_time_on_shelf(ticks_to_add)
            if curr_value <= 0.0:
                self.remove_food_from_shelf(curr_food.id)



def do_tick_housekeeping(time_between_ticks):
    time.sleep(time_between_ticks)

def process_new_item(shelves, curr_item: FoodItem):
    # Step 1 - see if can fit into proper shelf without dropping anything
    proper_shelf = shelves[curr_item.temp]
    dropped_item = proper_shelf.add_food_to_shelf(curr_item)
    pass

def create_shelves():
    hot_shelf = FoodShelf('hot', 10)
    cold_shelf = FoodShelf('cold', 10)
    frozen_shelf = FoodShelf('frozen', 10)
    overflow_shelf = FoodShelf('overflow', 15)

    shelves = {'hot': hot_shelf, 'cold': cold_shelf, 'frozen': frozen_shelf, 'overflow': overflow_shelf}
    return shelves

def tick_thread( time_between_ticks, number_per_tick, json_fn):
    total_ingested = 0
    shelves = create_shelves()
    with open(json_fn, 'r') as target:
        json_list = json.load(target)
    len_list = len(json_list)
    jsons = iter(json_list)

    while total_ingested < len_list:
        do_tick_housekeeping(time_between_ticks)
        for i in range(number_per_tick):
            curr_item = next(jsons)
            food_item = FoodItem(curr_item)
            total_ingested += 1
            process_new_item(shelves, food_item)
            if total_ingested >= len_list:
                break

if __name__ == "__main__":
    fn = 'orders.json'
    ingestion_df = read_json_file(fn)
    t = threading.Thread(target=tick_thread, args=(1, 2, fn,))
    t.start()

    pass