"""
Standalone Trend Discovery Script
Run: python -m agents.scripts.trend_discovery [--category "Self-Learning"]
"""
import argparse
import json
from agents.utils.trend_discovery import discover_trends, analyze_category


def main():
    parser = argparse.ArgumentParser(description='Trend Discovery for Children\'s Content')
    parser.add_argument('--category', help='Analyze specific category')
    args = parser.parse_args()

    if args.category:
        print(f"\n📊 Analyzing category: {args.category}")
        result = analyze_category(args.category)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("\n🔥 Discovering trending topics...")
        trends = discover_trends()
        print(f"\nFound {len(trends)} trending topics:\n")
        for t in trends:
            print(f"  📌 {t['title']}")
            print(f"     Category: {t['category']} | Volume: {t['search_volume']:,} | Growth: +{t['growth']}%")
            print(f"     Score: {t['score']}/100 | Competition: {t['competition']} | Format: {t['suggested_format']}")
            print(f"     Keywords: {', '.join(t['keywords'])}")
            print()

        print(json.dumps(trends, indent=2, default=str))


if __name__ == '__main__':
    main()
