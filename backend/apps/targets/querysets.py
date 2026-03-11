from django.db import models


class TargetQuerySet(models.QuerySet):

    def for_year(self, year):
        return self.filter(year=year)

    def for_qism(self, qism_id):
        return self.filter(qism_id=qism_id)

    def for_indicator(self, indicator_id):
        return self.filter(indicator_id=indicator_id)
