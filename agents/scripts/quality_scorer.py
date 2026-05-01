"""
Standalone Quality Scorer Agent
Run: python -m agents.scripts.quality_scorer --title "..." --category "..." --format shorts
"""
import argparse
import json
from agents.utils.quality_scorer import score_content, predict_performance

def main():
    parser = argparse.ArgumentParser(description='Quality Score & Performance Predictor')
    parser.add_argument('--title', required=True, help='Video title')
    parser.add_argument('--category', default='Self-Learning', help='Content category')
    parser.add_argument('--format', default='shorts', choices=['shorts', 'long'], help='Video format')
    parser.add_argument('--script', default='', help='Script content')
    parser.add_argument('--mode', default='both', choices=['score', 'predict', 'both'], help='Run mode')
    args = parser.parse_args()

    results = {}

    if args.mode in ('score', 'both'):
        print(f"\n🔍 Scoring: {args.title}")
        score = score_content(args.script, args.title, args.category, args.format)
        results['quality_score'] = score
        print(f"  Overall: {score['overall_score']}/100")
        print(f"  Recommendation: {score['recommendation']}")
        if score.get('flags'):
            print(f"  Flags: {', '.join(score['flags'])}")
        if score.get('feedback'):
            print(f"  Feedback: {score['feedback']}")

    if args.mode in ('predict', 'both'):
        print(f"\n🚀 Predicting: {args.title}")
        pred = predict_performance(args.title, args.category, args.format, args.script)
        results['prediction'] = pred
        print(f"  7-day views: {pred['predicted_views_7d']:,}")
        print(f"  30-day views: {pred['predicted_views_30d']:,}")
        print(f"  Virality: {pred['virality_score']}/100 ({pred['trending_match']})")
        print(f"  Engagement: {pred['predicted_engagement_rate']}%")
        print(f"  CTR: {pred['predicted_ctr']}%")

    print(f"\n{json.dumps(results, indent=2, default=str)}")
    return results

if __name__ == '__main__':
    main()
