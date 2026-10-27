"""Isolated DOM benchmark; never connects to an account or submits an order."""
import json
import statistics
import time

from test_dom_integration import NativeDomIntegrationTests
from flashsale.shopee import checkout_controls


def main():
    cls = NativeDomIntegrationTests
    cls.setUpClass()
    case = cls()
    try:
        case.setUp()
        case.checkout()
        case.session.bridge = case.bridge
        case.config['limit'] = 1000000

        def old_reads():
            case.session.verify_checkout_item(case.config)
            total, submit = checkout_controls(case.session.page)
            total.locator('xpath=following-sibling::*[1]').inner_text()
            submit.is_enabled()

        samples = {'before': [], 'after': []}
        for _ in range(30):
            for name, action in [('before', old_reads), ('after', lambda: case.session.verified_checkout_quote(case.config))]:
                started = time.perf_counter()
                action()
                samples[name].append((time.perf_counter()-started)*1000)
        print(json.dumps({'scope': 'Isolated local DOM; final validation only; no network or order',
                          'samples_per_path': 30, 'bridge_reads_before': 4, 'bridge_reads_after': 1,
                          'median_ms': {name: round(statistics.median(values), 3) for name, values in samples.items()}}))
    finally:
        if hasattr(case, 'dom'):
            case.tearDown()
        cls.tearDownClass()


if __name__ == '__main__':
    main()
