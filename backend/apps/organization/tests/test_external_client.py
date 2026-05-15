"""
اختبارات عميل النظام الخارجي للهيكل التنظيمي.

نُموَّك `requests.get` لتجنّب الاتصال الفعلي بالشبكة. كل اختبار يفحص
سيناريو واحد محدّداً ويتأكّد من السلوك المتوقّع.
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.organization.integrations.external_client import (
    ExternalOrgClient,
    ExternalOrgNotConfigured,
    ExternalOrgUnavailable,
)


def make_response(json_data=None, status_code=200, text=''):
    """Helper to build a fake requests.Response."""
    mock = MagicMock(spec=requests.Response)
    mock.status_code = status_code
    mock.ok = 200 <= status_code < 300
    mock.json.return_value = json_data if json_data is not None else {}
    mock.text = text
    return mock


class TestExternalOrgClientConfiguration:
    """اختبارات إعدادات العميل."""

    def test_not_configured_when_url_empty(self):
        client = ExternalOrgClient(base_url='', api_key='abc')
        assert client.is_configured() is False
        with pytest.raises(ExternalOrgNotConfigured):
            client.assert_configured()

    def test_not_configured_when_key_empty(self):
        client = ExternalOrgClient(base_url='http://x.com/api/', api_key='')
        assert client.is_configured() is False

    def test_configured_when_both_set(self):
        client = ExternalOrgClient(
            base_url='http://x.com/api/external/', api_key='key123'
        )
        assert client.is_configured() is True

    def test_base_url_normalized_with_trailing_slash(self):
        """`urljoin` يحتاج base_url ينتهي بـ / ليعمل الـ relative path."""
        client = ExternalOrgClient(
            base_url='http://x.com/api/external', api_key='key'
        )
        assert client.base_url.endswith('/')


@patch('apps.organization.integrations.external_client.requests.get')
class TestExternalOrgClientCalls:
    """اختبارات الاستدعاءات الفعليّة (مع mock)."""

    def _make_client(self):
        return ExternalOrgClient(
            base_url='http://x.com/api/external/',
            api_key='test-key',
            timeout=5,
        )

    def test_get_status_returns_json(self, mock_get):
        mock_get.return_value = make_response(
            {'status': 'active', 'total_units': 70}
        )
        client = self._make_client()

        result = client.get_status()

        assert result == {'status': 'active', 'total_units': 70}
        # نتأكّد من URL و headers
        called_url = mock_get.call_args[0][0]
        called_headers = mock_get.call_args[1]['headers']
        assert called_url == 'http://x.com/api/external/status/'
        assert called_headers['Authorization'] == 'ApiKey test-key'
        assert called_headers['Accept'] == 'application/json'

    def test_get_units_tree_returns_tree_list(self, mock_get):
        tree_response = {
            'tree': [
                {'id': 1, 'name': 'الدائرة الرئيسية', 'children': [
                    {'id': 2, 'name': 'مديرية أ', 'children': None},
                ]},
            ],
            'generated_at': '2026-05-16T10:00:00Z',
        }
        mock_get.return_value = make_response(tree_response)
        client = self._make_client()

        tree = client.get_units_tree()

        assert len(tree) == 1
        assert tree[0]['name'] == 'الدائرة الرئيسية'
        # نتأكّد من params الافتراضية: نُمرّر max_depth فقط — لا is_active
        # لأن `is_active=false` في النظام الخارجي = «المعطّلة فقط» (سلوك معكوس!)
        params = mock_get.call_args[1]['params']
        assert params['max_depth'] == 10
        assert 'is_active' not in params  # لجلب الكل (نشطة + معطّلة)

    def test_get_units_tree_active_only(self, mock_get):
        mock_get.return_value = make_response({'tree': []})
        client = self._make_client()

        client.get_units_tree(active_only=True)

        params = mock_get.call_args[1]['params']
        assert params['is_active'] == 'true'

    def test_get_unit_types_returns_results_list(self, mock_get):
        mock_get.return_value = make_response({
            'results': [
                {'id': 1, 'name': 'دائرة'},
                {'id': 2, 'name': 'مديرية'},
                {'id': 3, 'name': 'قسم'},
            ],
            'count': 3,
        })
        client = self._make_client()

        types = client.get_unit_types()

        assert len(types) == 3
        assert types[0]['name'] == 'دائرة'

    def test_get_units_list_full_detail(self, mock_get):
        mock_get.return_value = make_response({
            'results': [
                {'id': 1, 'name': 'وحدة', 'unit_type_name': 'دائرة'},
            ],
            'count': 1, 'page': 1, 'pages': 1, 'page_size': 100,
        })
        client = self._make_client()

        data = client.get_units_list(detail='full', page=1, page_size=100)

        assert 'results' in data
        params = mock_get.call_args[1]['params']
        assert params['detail'] == 'full'
        assert params['page'] == 1
        assert params['page_size'] == 100

    def test_get_unit_detail_uses_correct_path(self, mock_get):
        mock_get.return_value = make_response({'id': 5, 'name': 'وحدة'})
        client = self._make_client()

        client.get_unit_detail(5)

        called_url = mock_get.call_args[0][0]
        assert called_url == 'http://x.com/api/external/units/5/'


@patch('apps.organization.integrations.external_client.requests.get')
class TestExternalOrgClientErrors:
    """اختبارات معالجة الأخطاء."""

    def _make_client(self):
        return ExternalOrgClient(
            base_url='http://x.com/api/external/',
            api_key='test-key',
            timeout=5,
        )

    def test_401_raises_unavailable_with_arabic_message(self, mock_get):
        mock_get.return_value = make_response(status_code=401, text='Unauthorized')
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='غير صالح'):
            client.get_status()

    def test_403_raises_unavailable(self, mock_get):
        mock_get.return_value = make_response(status_code=403)
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='مرفوض'):
            client.get_status()

    def test_429_raises_unavailable(self, mock_get):
        mock_get.return_value = make_response(status_code=429)
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='الحدّ الأقصى'):
            client.get_status()

    def test_500_raises_unavailable(self, mock_get):
        mock_get.return_value = make_response(status_code=500)
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='خطأ خادم'):
            client.get_status()

    def test_timeout_raises_unavailable(self, mock_get):
        mock_get.side_effect = requests.Timeout()
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='مهلة الاتصال'):
            client.get_status()

    def test_connection_error_raises_unavailable(self, mock_get):
        mock_get.side_effect = requests.ConnectionError()
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='تعذّر الاتصال'):
            client.get_status()

    def test_invalid_json_raises_unavailable(self, mock_get):
        bad_response = MagicMock(spec=requests.Response)
        bad_response.status_code = 200
        bad_response.ok = True
        bad_response.json.side_effect = ValueError('not json')
        bad_response.text = 'plain text'
        mock_get.return_value = bad_response
        client = self._make_client()

        with pytest.raises(ExternalOrgUnavailable, match='JSON'):
            client.get_status()

    def test_call_without_config_raises_not_configured(self, mock_get):
        client = ExternalOrgClient(base_url='', api_key='')

        with pytest.raises(ExternalOrgNotConfigured):
            client.get_status()
        # `requests.get` لم يُستدعَ — منعنا الطلب قبل الشبكة
        mock_get.assert_not_called()
