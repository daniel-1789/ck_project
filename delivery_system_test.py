import unittest
import delivery_system
from delivery_system import shelves, curr_tick, create_shelves, FoodItem, process_new_item, NewItemStatus, courier_action
import json

class MyTestCase(unittest.TestCase):
    def build_full_dicts(self):
        global shelves
        shelves = create_shelves(10, 10, 10, 15)
        with open('orders.json', 'r') as target:
            json_list = json.load(target)
        len_list = len(json_list)
        jsons = iter(json_list)

        for i in range(len_list):
            curr_item = next(jsons)
            food_item = FoodItem(curr_item)
            process_new_item(shelves, food_item)

    def create_a_food_item(self):
        food_dict = dict()
        food_dict['id'] = 'unit-test'
        food_dict['name'] = 'Unit Test Sundae'
        food_dict['temp'] = 'frozen'
        food_dict['shelfLife'] = 30
        food_dict['decayRate'] = 10
        food_item = FoodItem(food_dict)
        return food_item

    def test_add_all_full(self):
        global shelves
        self.build_full_dicts()
        food_item = self.create_a_food_item()
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.moved_from_overflow)

    def test_add_dest_full(self):
        global shelves
        self.build_full_dicts()
        # remove an entry from the overflow
        shelves['overflow'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.moved_to_overflow)

    def test_add_dest_has_room(self):
        global shelves
        self.build_full_dicts()
        # remove an entry from the overflow
        shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)

    def test_add_no_matching_dict(self):
        global shelves
        self.build_full_dicts()
        # remove an entry from the overflow
        food_item = self.create_a_food_item()
        food_item.temp = 'absolute zero'
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.no_shelf)

    def setup_couriers(self, tick, food_item):
        couriers = dict()
        courier_time =  tick
        courier_slot = couriers.get(courier_time, [])
        courier_slot.append(food_item)
        couriers[courier_time] = courier_slot
        return couriers

    def test_courier_get_from_overflow_shelf(self):
        global shelves
        global curr_tick
        self.build_full_dicts()
        # remove an entry from the overflow
        shelves['overflow'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.moved_to_overflow)

        couriers = self.setup_couriers(curr_tick, food_item)
        retrieved_items = courier_action(shelves, couriers)
        pass
        removed_it = food_item in retrieved_items
        self.assertEqual(True, removed_it)

    def test_courier_get_from_right_shelf(self):
        global shelves
        global curr_tick
        self.build_full_dicts()
        # remove an entry from the overflow
        shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)

        couriers = self.setup_couriers(curr_tick, food_item)
        retrieved_items = courier_action(shelves, couriers)
        pass
        removed_it = food_item in retrieved_items
        self.assertEqual(True, removed_it)

    def test_courier_item_not_present(self):
        global shelves
        global curr_tick
        self.build_full_dicts()
        food_item = self.create_a_food_item()

        couriers = self.setup_couriers(curr_tick, food_item)
        retrieved_items = courier_action(shelves, couriers)
        removed_it = food_item in retrieved_items
        self.assertEqual(False, removed_it)

    def test_food_spoil(self):
        global shelves
        global curr_tick
        self.build_full_dicts()
        # remove an entry from the frozen
        shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        food_item.shelf_life = 1.0
        food_item.decay_rate = 0.5
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        shelves['frozen'].add_ticks(1)
        still_present = shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(True, still_present)

        shelves['frozen'].add_ticks(1)
        still_present = shelves['frozen'].food_dict.get(food_item.id, None) is not None
        pass
        self.assertEqual(False, still_present)

    def test_food_spoil_overflow_faster(self):
        global shelves
        global curr_tick
        self.build_full_dicts()
        # remove an entry from the overflow
        shelves['overflow'].food_dict.popitem()
        food_item = self.create_a_food_item()
        food_item.shelf_life = 1.0
        food_item.decay_rate = 0.5
        food_item.temp = 'overflow' # cheat a little to get it on overflow
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        shelves['overflow'].add_ticks(1)
        still_present = shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(False, still_present)

    def test_cheapest(self):
        global shelves
        global curr_tick
        self.build_full_dicts()
        # remove an entry from the frozen
        shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        food_item.value = 0.0000000001
        rc = process_new_item(shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        cheapest_id = shelves['frozen'].find_cheapest_item()
        self.assertEqual(cheapest_id, food_item.id)

if __name__ == '__main__':
    unittest.main()
