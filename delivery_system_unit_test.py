import unittest
from delivery_system import create_shelves, FoodItem, process_new_item, NewItemStatus, courier_action, \
    restore_to_proper_shelf
import json

curr_tick = 0

class MyTestCase(unittest.TestCase):
    def setUp(self):
        """
        Creates the class variable shelves - reads the default json file in and builds it - the idea is to
        make all the shelves full. We can then adjust them as required in individual tests.

        This assumes the json will fill all shelves if ingested all at once. This is the case with the
        orders.json we are using - and it has at least one of each type on the overflow shelf.
        :return:
        """
        self.shelves = create_shelves(10, 10, 10, 15)
        with open('orders.json', 'r') as target:
            json_list = json.load(target)
        len_list = len(json_list)
        jsons = iter(json_list)

        for i in range(len_list):
            curr_item = next(jsons)
            food_item = FoodItem(curr_item)
            process_new_item(self.shelves, food_item)

    def create_a_food_item(self):
        """
        Creates a FoodItem to later allow a new order being put on shelf
        :return:
        """
        food_dict = dict()
        food_dict['id'] = 'unit-test'
        food_dict['name'] = 'Unit Test Sundae'
        food_dict['temp'] = 'frozen'
        food_dict['shelfLife'] = 30
        food_dict['decayRate'] = 10
        food_item = FoodItem(food_dict)
        return food_item

    def test_add_all_full(self):
        """
        Attempt to add an item to the frozen shelf - no room - remove an item from overflow and put it there
        :return:
        """
        food_item = self.create_a_food_item()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.removed_item_for_room)
        found_it = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(found_it, True)

    def test_add_already_present(self):
        """
        Test that code can detect an attempt to add an item to a shelf when item is already on a shelf
        :return:
        """
        food_item = self.create_a_food_item()
        # remove an entry from the frozen
        self.shelves['frozen'].food_dict.popitem()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        food_item_dup = self.create_a_food_item()
        food_item_dup.temp = 'hot'
        rc = process_new_item(self.shelves, food_item_dup)
        self.assertEqual(rc, NewItemStatus.already_shelved)

    def test_add_dest_full(self):
        """
        Destination shelf is full. Overflow shelf has room. Make sure goes into right shelf and
        bump to overflow
        :return:
        """
        # remove an entry from the overflow
        self.shelves['overflow'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.moved_item_to_overflow)
        found_it = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(found_it, True)

    def test_add_dest_has_room(self):
        """
        Destination shelf has room. Nothing needs to go to overflow or be dropped.
        :return:
        """
        # remove an entry from the frozen
        self.shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        found_it = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(found_it, True)

    def test_add_dest_is_empty(self):
        """
        Destination shelf is empty. Nothing needs to go to overflow or be dropped.
        :return:
        """
        # remove an entry from the frozen
        self.shelves['frozen'].food_dict = dict()  # destroy the old dict
        food_item = self.create_a_food_item()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        found_it = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(found_it, True)
        self.assertEqual(1, len(self.shelves['frozen'].food_dict))


    def test_add_no_matching_dict(self):
        """
        Attempt to add to a non-existent shelf
        :return:
        """
        food_item = self.create_a_food_item()
        food_item.temp = 'absolute zero'
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.no_shelf)

    def test_add_dest_full_restore_from_overflow(self):
        """
        Overflow is full. Remove an item from hot so overflow can move an item there
        :return:
        """
        # remove an entry from the hot - this will give us space for the overflow to rearrange
        self.shelves['hot'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.restored_from_overflow)
        found_it = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(found_it, True)

    def setup_couriers(self, tick, food_item):
        """
        Create a mini-courier dict
        :param tick: current time in ticks
        :param food_item: food_item to add to mini-courier
        :return: courier dictionary with just one entry
        """
        couriers = dict()
        courier_time =  tick
        courier_slot = couriers.get(courier_time, [])
        courier_slot.append(food_item)
        couriers[courier_time] = courier_slot
        return couriers

    def test_courier_get_from_overflow_shelf(self):
        """
        verify the courier gets an entry that is on overflow
        :return:
        """
        # remove an entry from the overflow
        self.shelves['overflow'].food_dict.popitem()
        food_item = self.create_a_food_item()
        self.shelves['overflow'].food_dict = dict()  # destroy the old dict
        rc = process_new_item(self.shelves, food_item)
        now_on_overflow = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_overflow, True)

        couriers = self.setup_couriers(curr_tick, food_item)
        retrieved_items = courier_action(self.shelves, couriers)
        removed_it = food_item in retrieved_items
        self.assertEqual(True, removed_it)
        now_on_overflow = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_overflow, False)

    def test_courier_get_from_right_shelf(self):
        """
        verify the courier gets an entry that is on the proper shelf
        :return:
        """
        global curr_tick
        # remove an entry from the overflow
        self.shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        now_on_frozen = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_frozen, True)

        couriers = self.setup_couriers(curr_tick, food_item)
        retrieved_items = courier_action(self.shelves, couriers)
        removed_it = food_item in retrieved_items
        self.assertEqual(True, removed_it)
        now_on_frozen = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_frozen, False)

    def test_courier_item_not_present(self):
        """
        Verify courier fails at getting a non-existent item
        :return:
        """
        global curr_tick
        food_item = self.create_a_food_item()  # do not insert this one onto a shelf

        couriers = self.setup_couriers(curr_tick, food_item)
        retrieved_items = courier_action(self.shelves, couriers)
        removed_it = food_item in retrieved_items
        self.assertEqual(False, removed_it)

    def test_food_spoil(self):
        """
        Force food to spoil, detect it is removed
        :return:
        """
        global curr_tick
        # remove an entry from the frozen
        self.shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        food_item.shelf_life = 1.0
        food_item.decay_rate = 0.5
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        self.shelves['frozen'].add_ticks(1)
        still_present = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(True, still_present)

        self.shelves['frozen'].add_ticks(1)
        still_present = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(False, still_present)

    def test_food_spoil_overflow_faster(self):
        """
        Verify the overflow shelf spoils faster
        :return:
        """
        global curr_tick
        # remove an entry from the overflow
        self.shelves['overflow'].food_dict.popitem()
        food_item = self.create_a_food_item()
        food_item.shelf_life = 1.0
        food_item.decay_rate = 0.5
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.moved_item_to_overflow)
        self.shelves['overflow'].add_ticks(1)
        still_present = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(False, still_present)

    def test_cheapest(self):
        """
        Test that the cheapest item can be found - note we don't use the cheapest as a determination as to
        what to throw out but I have experimented with doing so.
        :return:
        """
        # remove an entry from the frozen
        self.shelves['frozen'].food_dict.popitem()
        food_item = self.create_a_food_item()
        food_item.value = 0.0000000001
        rc = process_new_item(self.shelves, food_item)
        self.assertEqual(rc, NewItemStatus.ok)
        cheapest_id = self.shelves['frozen'].find_cheapest_item()
        self.assertEqual(cheapest_id, food_item.id)

    def test_restore_all(self):
        """
        Test that rebalancing will move things to proper shelf if there is room -
        this code is not in use in the main code but would be a useful addition
        :return:
        """
        food_item = self.create_a_food_item()

        self.shelves['overflow'].food_dict = dict()  # destroy the old dict
        self.shelves['overflow'].food_dict[food_item.id] = food_item  # force it on the overflow

        now_on_frozen = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_frozen, False)
        now_on_standby = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_standby, True)

        self.shelves['frozen'].food_dict = dict()  # destroy the old dict
        restore_to_proper_shelf(self.shelves)  # this should move it to the frozen shelf

        now_on_frozen = self.shelves['frozen'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_frozen, True)
        now_on_standby = self.shelves['overflow'].food_dict.get(food_item.id, None) is not None
        self.assertEqual(now_on_standby, False)


if __name__ == '__main__':
    unittest.main()
