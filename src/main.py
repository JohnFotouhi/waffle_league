import os

from data.analyzer import DataAnalyzer

def get_league_creds():
    league_id = os.getenv('league_id')
    espn_s2 = os.getenv('s2')
    swid = os.getenv('swid')

    if not espn_s2 or not swid or not league_id:
        raise ValueError("League credentials are not properly set in environment variables.")

    return league_id, espn_s2, swid

def main():
    league_id, espn_s2, swid = get_league_creds()
    analyzer = DataAnalyzer(league_id=league_id, espn_s2=espn_s2, swid=swid)
    analyzer.get_data(start_year=2023, end_year=2025)

    lowest_winning_points = analyzer.lowest_winning_point_totals()

    highest_losing_points = analyzer.highest_losing_point_total()

    highest_scores = analyzer.highest_score_all_time()

    lowest_scores = analyzer.lowest_score_all_time()

    closest_games = analyzer.closest_game()

    lifetime_top_scorers = analyzer.lifetime_top_scorers(None)

    season_points_allowed = analyzer.season_points_allowed(2023, 2024)


if __name__ == "__main__":
    main()