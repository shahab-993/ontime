class AbstractDate:
    """
    Abstract class representing a date.
    """

    def __init__(self, year=None, month=None, day_of_month=None, jdn=None, date=None):
        if jdn is not None:
            result = self.from_jdn(jdn)
            self.year = result[0]
            self.month = result[1]
            self.day_of_month = result[2]
        elif date is not None:
            jdn = date.to_jdn()
            result = self.from_jdn(jdn)
            self.year = result[0]
            self.month = result[1]
            self.day_of_month = result[2]
        else:
            self.year = year
            self.month = month
            self.day_of_month = day_of_month

    def component1(self):
        return self.year

    def component2(self):
        return self.month

    def component3(self):
        return self.day_of_month

    def to_jdn(self):
        raise NotImplementedError("Subclasses must implement this method")

    def from_jdn(self, jdn):
        raise NotImplementedError("Subclasses must implement this method")

    def __eq__(self, other):
        if other is None or not isinstance(other, AbstractDate):
            return False
        return self.year == other.year and self.month == other.month and self.day_of_month == other.day_of_month

    def __hash__(self):
        result = self.year
        result = 31 * result + self.month
        result = 31 * result + self.day_of_month
        return result
