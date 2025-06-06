import scrapy
from scrapy.http import JsonRequest

from locations.categories import Categories, apply_category
from locations.geo import point_locations
from locations.hours import OpeningHours
from locations.items import Feature


class UspsSpider(scrapy.Spider):
    name = "usps"
    item_attributes = {"operator": "United States Postal Service", "operator_wikidata": "Q668687"}

    def start_requests(self):
        for lat, lon in point_locations("us_centroids_25mile_radius.csv"):
            yield JsonRequest(
                url="https://tools.usps.com/UspsToolsRestServices/rest/POLocator/findLocations",
                data={"requestGPSLat": lat, "requestGPSLng": lon, "maxDistance": "100", "requestType": "PO"},
            )

    @staticmethod
    def parse_hours(rules) -> OpeningHours:
        opening_hours = OpeningHours()

        for rule in rules:
            for time in rule["times"]:
                opening_hours.add_range(
                    day=rule["dayOfTheWeek"], open_time=time["open"], close_time=time["close"], time_format="%H:%M:%S"
                )

        return opening_hours

    def parse(self, response, **kwargs):
        for store in response.json().get("locations", []):
            if zip4 := store.get("zip4"):
                postcode = store["zip5"] + "-" + zip4
            else:
                postcode = store["zip5"]
            properties = {
                "ref": store["locationID"],
                "name": store["locationName"],
                "street_address": store["address1"],
                "city": store["city"],
                "state": store["state"],
                "postcode": postcode,
                "country": "US",
                "lat": store["latitude"],
                "lon": store["longitude"],
                "phone": store["phone"],
            }
            for service in store["locationServiceHours"]:
                if service["name"] == "BUSINESS":
                    properties["opening_hours"] = self.parse_hours(service["dailyHoursList"])
                    break

            apply_category(Categories.POST_OFFICE, properties)

            yield Feature(**properties)
