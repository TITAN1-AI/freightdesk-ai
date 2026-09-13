"""Owner-authorized local historical staging; no network and no commit option."""
import argparse

from app.core.runtime import RuntimePaths
from app.services.ascend_staging import AscendRealStager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='CSV filename already in the approved runtime inbox')
    options = parser.parse_args()
    source = RuntimePaths.from_environment().path('Data','booking-logistics','history','inbox',options.filename)
    report, target = AscendRealStager().stage(source)
    print(f"Staged {report['rows']} rows; validation_passed={report['validation_passed']}; committed_rows=0.")
    print(f"Row errors={report['rows_with_errors']}; identifier warnings={report['rows_with_identifier_warnings']}; "
          f"anchor mismatches={len(report['anchor_mismatches'])}; version conflicts={report['prior_version_conflicts']}.")
    print('Sanitized staging report: '+str(target/'staging-report.md'))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Ascend staging stopped safely. No commit occurred; source details are not printed.') from None
