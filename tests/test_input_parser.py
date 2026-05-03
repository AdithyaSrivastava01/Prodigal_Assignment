from __future__ import annotations

from payment_agent.input_parser import InputParser


class TestExtractAccountId:
    def setup_method(self):
        self.parser = InputParser()

    def test_plain_id(self):
        assert self.parser.extract_account_id("ACC1001") == "ACC1001"

    def test_in_sentence(self):
        assert self.parser.extract_account_id("My account ID is ACC1001") == "ACC1001"

    def test_lowercase(self):
        assert self.parser.extract_account_id("acc1001") == "ACC1001"

    def test_no_match(self):
        assert self.parser.extract_account_id("hello") is None

    def test_with_greeting(self):
        assert self.parser.extract_account_id("Hi, my account is ACC1002") == "ACC1002"


class TestExtractNameFromContext:
    def setup_method(self):
        self.parser = InputParser()

    def test_plain_name(self):
        assert self.parser.extract_name_from_context("Nithin Jain") == "Nithin Jain"

    def test_with_prefix_my_name_is(self):
        assert (
            self.parser.extract_name_from_context("My name is Nithin Jain")
            == "Nithin Jain"
        )

    def test_with_prefix_i_am(self):
        assert (
            self.parser.extract_name_from_context("I am Nithin Jain") == "Nithin Jain"
        )

    def test_with_prefix_im(self):
        assert self.parser.extract_name_from_context("I'm Nithin Jain") == "Nithin Jain"

    def test_normalizes_whitespace(self):
        assert (
            self.parser.extract_name_from_context("  Nithin   Jain  ") == "Nithin Jain"
        )


class TestExtractNameFromAny:
    def setup_method(self):
        self.parser = InputParser()

    def test_with_prefix(self):
        assert self.parser.extract_name_from_any("I'm Nithin Jain") == "Nithin Jain"

    def test_without_prefix_returns_none(self):
        assert self.parser.extract_name_from_any("Nithin Jain") is None

    def test_with_name_colon(self):
        assert self.parser.extract_name_from_any("name: Nithin Jain") == "Nithin Jain"


class TestExtractSecondaryFactors:
    def setup_method(self):
        self.parser = InputParser()

    def test_dob(self):
        factors = self.parser.extract_secondary_factors("My DOB is 1990-05-14")
        assert factors == {"dob": "1990-05-14"}

    def test_pincode(self):
        factors = self.parser.extract_secondary_factors("pincode 400001")
        assert factors == {"pincode": "400001"}

    def test_aadhaar(self):
        factors = self.parser.extract_secondary_factors("aadhaar last 4: 4321")
        assert factors == {"aadhaar_last4": "4321"}

    def test_bare_4_digits(self):
        factors = self.parser.extract_secondary_factors("4321")
        assert factors.get("aadhaar_last4") == "4321"

    def test_bare_6_digits(self):
        factors = self.parser.extract_secondary_factors("400001")
        assert factors.get("pincode") == "400001"

    def test_no_factors(self):
        factors = self.parser.extract_secondary_factors("hello world")
        assert factors == {}

    def test_multiple_factors(self):
        factors = self.parser.extract_secondary_factors(
            "DOB 1990-05-14 and aadhaar 4321"
        )
        assert "dob" in factors
        assert "aadhaar_last4" in factors


class TestExtractAmount:
    def setup_method(self):
        self.parser = InputParser()

    def test_plain_number(self):
        assert self.parser.extract_amount("500") == 500.0

    def test_with_decimal(self):
        assert self.parser.extract_amount("500.50") == 500.50

    def test_with_rupee_symbol(self):
        assert self.parser.extract_amount("\u20b9500") == 500.0

    def test_with_rs(self):
        assert self.parser.extract_amount("Rs. 500") == 500.0

    def test_full_keyword(self):
        assert self.parser.extract_amount("full", balance=1250.75) == 1250.75

    def test_all_keyword(self):
        assert self.parser.extract_amount("pay all", balance=1250.75) == 1250.75

    def test_no_amount(self):
        assert self.parser.extract_amount("hello") is None

    def test_in_sentence(self):
        assert self.parser.extract_amount("I want to pay 500") == 500.0


class TestExtractCardDetails:
    def setup_method(self):
        self.parser = InputParser()

    def test_all_at_once_labeled(self):
        text = "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027"
        details = self.parser.extract_card_details(text)
        assert details.get("cardholder_name") == "Nithin Jain"
        assert details.get("card_number") == "4532015112830366"
        assert details.get("cvv") == "123"
        assert details.get("expiry_month") == 12
        assert details.get("expiry_year") == 2027

    def test_card_number_with_spaces(self):
        details = self.parser.extract_card_details("4532 0151 1283 0366")
        assert details.get("card_number") == "4532015112830366"

    def test_expiry_two_digit_year(self):
        details = self.parser.extract_card_details("12/27")
        assert details.get("expiry_month") == 12
        assert details.get("expiry_year") == 2027

    def test_cvv_standalone(self):
        details = self.parser.extract_card_details("123")
        assert details.get("cvv") == "123"

    def test_multiline(self):
        text = "Cardholder: Nithin Jain\n4532015112830366\nCVV: 123\n12/2027"
        details = self.parser.extract_card_details(text)
        assert details.get("cardholder_name") is not None
        assert details.get("card_number") == "4532015112830366"
        assert details.get("cvv") == "123"
        assert details.get("expiry_month") == 12


class TestIsDecline:
    def setup_method(self):
        self.parser = InputParser()

    def test_no(self):
        assert self.parser.is_decline("no") is True

    def test_cancel(self):
        assert self.parser.is_decline("I want to cancel") is True

    def test_affirmative_not_decline(self):
        assert self.parser.is_decline("yes") is False


class TestIsAffirmative:
    def setup_method(self):
        self.parser = InputParser()

    def test_yes(self):
        assert self.parser.is_affirmative("yes") is True

    def test_sure(self):
        assert self.parser.is_affirmative("sure, go ahead") is True

    def test_negative_not_affirmative(self):
        assert self.parser.is_affirmative("no thanks") is False
