from abc import ABC, abstractmethod

class YearMonthDate(ABC):

    @abstractmethod
    def month_start_of_months_distance(self, months_distance: int):
        pass

    @abstractmethod
    def months_distance_to(self, date):
        pass