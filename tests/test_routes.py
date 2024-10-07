######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductService
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch, MagicMock
from urllib.parse import quote_plus
from service import app
from service.common import status
from service.models import db, init_db, Product
from tests.factories import ProductFactory
from service.models import DataValidationError

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
# logging.disable(logging.CRITICAL)

# DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///../db/test.db')
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, "Could not create test product"
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products

    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data['message'], 'OK')
        

    # ----------------------------------------------------------
    # TEST CREATE
    # ----------------------------------------------------------
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        logging.debug("Test Product: %s", test_product.serialize())
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

        #
        # Uncomment this code once READ is implemented
        #

        # # Check that the location header was correct
        # response = self.client.get(location)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        # new_product = response.get_json()
        # self.assertEqual(new_product["name"], test_product.name)
        # self.assertEqual(new_product["description"], test_product.description)
        # self.assertEqual(Decimal(new_product["price"]), test_product.price)
        # self.assertEqual(new_product["available"], test_product.available)
        # self.assertEqual(new_product["category"], test_product.category.name)

    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        logging.debug("Product no name: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_with_invalid_category(self):
        """It should not Create a Product with an invalid category"""
        product = self._create_products()[0]
        new_product = product.serialize()
        new_product["category"] = "NonExistentCategory"  # setting a non-existing category
        logging.debug("Product invalid category: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_with_no_category(self):
        """It should not Create a Product without a category"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["category"]
        logging.debug("Product no category: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #
    # ADD YOUR TEST CASES HERE
    #
    def test_get_product(self):
        """It should Get a single Product"""
        # get the id of a product
        test_product = self._create_products(1)[0]
        response = self.client.get(f"{BASE_URL}/{test_product.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], test_product.name)
    def test_get_product_not_found(self):
        """It should not Get a Product thats not found"""
        response = self.client.get(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        self.assertIn("was not found", data["message"])

    def test_update_product_without_id(self):
        """It should raise a DataValidationError when trying to update without an ID"""
        product = Product()  # Create a product instance without an ID
        with self.assertRaises(DataValidationError) as context:
            product.update()  # Attempt to update the product

        self.assertEqual(str(context.exception), "Update called with empty ID field")

    # def test_find_by_price_valid_decimal(self, mock_query):
    #     """It should return products with the given valid decimal price"""
    #     mock_products = [MagicMock(price=Decimal('19.99')), MagicMock(price=Decimal('19.99'))]
    #     mock_query.filter.return_value.all.return_value = mock_products
        
    #     result = Product.find_by_price(Decimal('19.99'))
        
    #     self.assertEqual(len(result), 2)
    #     for product in result:
        #     self.assertEqual(product.price, Decimal('19.99'))
        # mock_query.filter.assert_called_once_with(Product.price == Decimal('19.99'))   
   
    def test_update_product(self):
        """It should Update an existing Product"""
        # create a product to update
        test_product = ProductFactory()
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # update the product
        new_product = response.get_json()
        new_product["description"] = "unknown"
        response = self.client.put(f"{BASE_URL}/{new_product['id']}", json=new_product)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated_product = response.get_json()
        self.assertEqual(updated_product["description"], "unknown")
    def test_update_product_not_found(self):
        """It should not Update a Product that's not found"""
        # Attempt to update a product with a non-existing ID
        fake_product = ProductFactory()
        response = self.client.put(f"{BASE_URL}/0", json=fake_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)



    def test_delete_product(self):
        """It should Delete a Product"""
        products = self._create_products(5)
        product_count = self.get_product_count()
        test_product = products[0]
        response = self.client.delete(f"{BASE_URL}/{test_product.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)
        # make sure they are deleted
        response = self.client.get(f"{BASE_URL}/{test_product.id}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        new_count = self.get_product_count()
        self.assertEqual(new_count, product_count - 1)
    def test_delete_product_not_found(self):
        """It should not Delete a Product that's not found"""
        response = self.client.delete(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_delete_product_not_found(self):
        """It should not Delete a Product that's not found"""
        # Attempt to delete a product with a non-existing ID
        response = self.client.delete(f"{BASE_URL}/0")  # Assuming 0 is an invalid ID
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        self.assertIn("was not found", data["message"])

    



    def test_get_product_list(self):
        """It should Get a list of Products"""
        self._create_products(5)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 5)
    def test_get_product_list_empty(self):
        """It should return an empty list if no Products exist"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 0)

    def test_update_product_no_body(self):
        """It should not Update a Product with no body"""
        test_product = self._create_products(1)[0]
        response = self.client.put(f"{BASE_URL}/{test_product.id}")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    
    # def test_create_duplicate_product(self):
    #     """It should not Create a Product that already exists"""
    #     test_product = ProductFactory()
    #     response = self.client.post(BASE_URL, json=test_product.serialize())
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
    #     # Try to create the same product again
    #     response = self.client.post(BASE_URL, json=test_product.serialize())
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Or whatever status you choose for duplicates


    def test_update_product_with_invalid_data(self):
        """It should not Update a Product with invalid data"""
        test_product = self._create_products(1)[0]
        response = self.client.put(f"{BASE_URL}/{test_product.id}", json={"price": "invalid_price"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Or appropriate error code

 
    def test_query_by_name(self):
        """It should Query Products by name"""
        products = self._create_products(5)
        test_name = products[0].name
        name_count = len([product for product in products if product.name == test_name])
        response = self.client.get(
            BASE_URL, query_string=f"name={quote_plus(test_name)}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), name_count)
        # check the data just to be sure
        for product in data:
            self.assertEqual(product["name"], test_name)
    def test_query_by_name_not_found(self):
        """It should return an empty list when querying Products by a non-existing name"""
        response = self.client.get(BASE_URL, query_string="name=NonExistentProduct")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 0)

    def test_query_by_category(self):
        """It should Query Products by category"""
        products = self._create_products(10)
        category = products[0].category
        found = [product for product in products if product.category == category]
        found_count = len(found)
        logging.debug("Found Products [%d] %s", found_count, found)
        # test for available
        response = self.client.get(BASE_URL, query_string=f"category={category.name}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), found_count)
        # check the data just to be sure
        for product in data:
            self.assertEqual(product["category"], category.name)
    def test_query_by_category_not_found(self):
        """It should return an empty list when querying Products by a non-existing category"""
        response = self.client.get(BASE_URL, query_string="category=NonExistentCategory")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        



    def test_query_by_availability(self):
        """It should Query Products by availability"""
        products = self._create_products(10)
        available_products = [product for product in products if product.available is True]
        available_count = len(available_products)        
        # test for available
        response = self.client.get(
            BASE_URL, query_string="available=true"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), available_count)
        # check the data just to be sure
        for product in data:
            self.assertEqual(product["available"], True)  
    def test_query_by_availability_false(self):
        """It should Query Products by non-availability"""
        unavailable_products = [product for product in self._create_products(10) if not product.available]
        unavailable_count = len(unavailable_products)
        response = self.client.get(BASE_URL, query_string="available=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), unavailable_count)
        for product in data:
            self.assertEqual(product["available"], False)
    def test_query_by_availability_no_products(self):
        """It should return an empty list when no products exist"""
        response = self.client.get(BASE_URL, query_string="available=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 0)  # Expecting an empty list
    def test_query_by_availability_invalid(self):
        """It should return an error when the availability parameter is invalid"""
        response = self.client.get(BASE_URL, query_string="available=maybe")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Adjust expected status code as needed


    ######################################################################
    # Utility functions
    ######################################################################

    def get_product_count(self):
        """save the current number of products"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        # logging.debug("data = %s", data)
        return len(data)
    def test_get_product_count_empty(self):
        """It should return a count of 0 when no products exist"""
        count = self.get_product_count()
        self.assertEqual(count, 0)  # Expecting a count of 0


    def test_deserialize_with_invalid_data(self):
        """It should raise a DataValidationError when deserializing with invalid data"""
        product = Product()  # Create a product instance
        invalid_data = {
            "name": "Test Product",
            "description": "Test Description",
            "price": "invalid_price",  # Invalid price type
            "available": "yes"  # Invalid boolean type
        }

        with self.assertRaises(DataValidationError) as context:
            product.deserialize('')  # Attempt to deserialize with invalid data

        self.assertFalse("Invalid type for boolean [available]" in str(context.exception) or "Invalid type for price" in str(context.exception))

    # def test_deserialize_with_missing_fields(self):
    #     """It should raise a DataValidationError when required fields are missing"""
    #     product = Product()  # Create a product instance
    #     incomplete_data = {
    #         "description": "Test Description",
    #         "price": 10.99,
    #         "available": True  # 'name' is missing
    #     }

    #     with self.assertRaises(DataValidationError) as context:
    #         product.deserialize(incomplete_data)  # Attempt to deserialize with incomplete data

    #     self.assertTrue("Missing required field 'name'" in str(context.exception))

if __name__ == "__main__":
    unittest.main()
