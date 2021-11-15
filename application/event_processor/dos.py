import random
from logging import getLogger
from os import environ, getenv
from typing import Any, List

from boto3 import client
from nhs import NHSEntity
from psycopg2 import connect

log = getLogger("lambda")
secrets_manager = client("secretsmanager", region_name=getenv("AWS_REGION", default="eu-west-2"))
VALID_SERVICE_TYPES = {13, 131, 132, 134, 137}
VALID_STATUS_ID = 1


class DoSService:
    """Class to represent a DoSService"""

    # These values are which columns are selected from the database and then
    # are passed in as attributes into the DoSService object.
    #
    # example: Put 'postcode' in this list and you can use service.postcode in
    # the object
    db_columns = [
        "id",
        "uid",
        "name",
        "odscode",
        "address",
        "town",
        "postcode",
        "web",
        "email",
        "fax",
        "nonpublicphone",
        "typeid",
        "parentid",
        "subregionid",
        "statusid",
        "createdtime",
        "modifiedtime",
        "publicphone",
        "publicname",
    ]

    def __init__(self, db_cursor_row):
        """Sets the attributes of this object to those found in the db row"""
        for i, attribute_name in enumerate(self.db_columns):
            attrbute_value = db_cursor_row[i]
            setattr(self, attribute_name, attrbute_value)

    def __repr__(self):
        """Returns a string representation of this object"""
        if self.publicname is not None:
            name = self.publicname
        elif self.name is not None:
            name = self.name
        else:
            name = "NO-VALID-NAME"

        return f"<uid={self.uid} ods={self.odscode} type={self.typeid} status={self.statusid} name='{name}'>"

    def ods5(self) -> str:
        """First 5 digits of odscode"""
        return self.odscode[0:5]

    def get_changes(self, nhs_entity: NHSEntity) -> dict:
        """Returns a dict of the changes that are required to get
        the service inline with the given nhs_entity
        """
        changes = {}
        changes = add_to_change_request_if_not_equal(changes, "website", self.web, nhs_entity.Website)
        changes = add_to_change_request_if_not_equal(changes, "postcode", self.postcode, nhs_entity.Postcode)
        changes = add_to_change_request_if_not_equal(changes, "publicphone", self.publicphone, nhs_entity.Phone)
        changes = add_to_change_request_if_not_equal(
            changes, "publicname", self.publicname, nhs_entity.OrganisationName
        )
        return changes


def add_to_change_request_if_not_equal(changes: dict, change_key: str, dos_value: Any, nhs_uk_value: Any) -> dict:
    if compare_values(dos_value, nhs_uk_value):
        changes[change_key] = nhs_uk_value
    return changes


def compare_values(dos_value: Any, nhs_uk_value: Any) -> bool:
    """Compare if two values are equal. Values are converted to string and compared.

    Args:
        dos_value (Any): First value to compare
        nhs_uk_value (Any): Second value to compare

    Returns:
        bool: False if equal, True if not equal
    """
    not_equal = False
    if str(dos_value) != str(nhs_uk_value):
        not_equal = True
    return not_equal


def get_addresses(nhs_uk_entity: NHSEntity, dos_service: DoSService) -> tuple:
    """Returns a tuple of the address and postcode of the nhs_uk_entity and dos_service"""
    nhs_uk_address = ""
    dos_address = ""
    return nhs_uk_address, dos_address


def dummy_dos_service() -> DoSService:
    """Creates a DoSService Object with random data for the unit testing"""
    test_data = []
    for col in DoSService.db_columns:
        random_str = "".join(random.choices("ABCDEFGHIJKLM", k=8))
        test_data.append(random_str)
    return DoSService(test_data)


def get_matching_dos_services(odscode: str) -> List[DoSService]:
    """Retrieves DoS Services from DoS database

    input:  ODSCode

    output: List of DoSService objects with matching first 5 digits

            of ODSCode, taken from DoS database
    """

    log.info(f"Searching for DoS services with ODSCode that matches first 5 digits of '{odscode}'")

    # Get DB details from env variables
    server = environ["DB_SERVER"]
    port = environ["DB_PORT"]
    db_name = environ["DB_NAME"]
    db_user = environ["DB_USER_NAME"]
    secret_name = environ["DB_SECRET_NAME"]

    # Collect the DB password from AWS secrets manager
    secret_response = secrets_manager.get_secret_value(SecretId=secret_name)
    password = secret_response["SecretString"]
    # Connect to Database
    log.info(f"Attempting connection to database '{server}'")
    log.debug(f"host={server}, port={port}, dbname={db_name}, user={db_user}, password={password}")
    db = psycopg2.connect(host=server, port=port, dbname=db_name, user=db_user, password=password, connect_timeout=30)

    # Create and run SQL Command with inputted odscode SELECTING columns
    # defined at top of file and using the 'LIKE' command to match first
    # 5 digits of ODSCode
    sql_command = f"SELECT {', '.join(DoSService.db_columns)} FROM services WHERE odscode LIKE '{odscode[0:5]}%'"
    log.info(f"Created SQL command to run: {sql_command}")
    c = db.cursor()
    c.execute(sql_command)
    # Create list of DoSService objects from returned rows
    services = [DoSService(row) for row in c.fetchall()]
    return services
