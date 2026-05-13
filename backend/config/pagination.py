"""
Paginator مخصّص يسمح للعميل بتحديد حجم الصفحة عبر ?page_size=N.
يُطبّق حد أقصى للأمان.
"""
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000
