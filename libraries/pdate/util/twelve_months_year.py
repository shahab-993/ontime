from libraries.pdate.abstract_date import AbstractDate

class TwelveMonthsYear:
    @staticmethod
    def month_start_of_months_distance(base_date: AbstractDate, months_distance: int, create_date):
        """
        Returns the date at the start of the month after a given number of months from the base date.
        
        :param base_date: The base date to start from.
        :param months_distance: The number of months to move.
        :param create_date: A function to create a date object.
        :return: The new date at the start of the calculated month.
        """
        month = months_distance + base_date.month - 1  # make it zero-based for easier calculations
        year = base_date.year + (month // 12)
        month %= 12
        if month < 0:
            year -= 1
            month += 12
        return create_date(year, month + 1, 1)

    @staticmethod
    def months_distance_to(base_date: AbstractDate, to_date: AbstractDate) -> int:
        """
        Calculates the number of months between the base date and the target date.
        
        :param base_date: The starting date.
        :param to_date: The target date.
        :return: The number of months between the two dates.
        """
        return ((to_date.year - base_date.year) * 12) + to_date.month - base_date.month
