from dataclasses import dataclass
import logging
import sys
import signal
from espn_api.football import Team, League
from espn_api.requests.espn_requests import ESPNInvalidLeague

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fantasy_analytics.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

@dataclass
class DateMatchup:
    """Matchup class but also holds week and year."""
    winner: Team
    winner_score: int
    loser: Team
    loser_score: int
    difference: int
    is_playoff: bool
    matchup_type: str
    week: int
    year: int

@dataclass
class DateActivity:
    """Activity class but also holds year."""
    actions: list
    date: int # Epoch time milliseconds
    year: int
    week: int

class DataAnalyzer:
    """Class to collect and process data for insights."""
    def __init__(self, league_id: int, espn_s2: str, swid: str):
        self.espn_s2 = espn_s2
        self.swid = swid
        self.league_id = league_id
        self.matchups = []
        self.activities = []
        self.output_file = "waffle_league_analysis.txt"
         
    def _write_to_file(self, content: str, append: bool = True):
        """Write content to the output text file."""
        mode = 'a' if append else 'w'
        with open(self.output_file, mode, encoding='utf-8') as f:
            f.write(content + '\n')
         
    def get_data(self, start_year: int, end_year: int):
        for year in range(start_year, end_year + 1):
            logger.info(f"Making API call for league year: {year}")
            league = League(league_id=self.league_id, year=year, espn_s2=self.espn_s2, swid=self.swid)
            logger.info(f"Finished API call for league year: {year}")
            self._get_matchups(league, year)
            # self._get_activities(league, year)

    def _get_matchups(self, league, year, timeout_seconds: int = 30):
        """Collect matchups from for a given league year."""
        for week in range(1, league.current_week):

            logger.info(f"Getting matchups for week {week} of {year}")
            for retry in range(3):
                try:
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(timeout_seconds)
                    weekly_matchups = league.scoreboard(week)
                    signal.alarm(0)
                    break
                except TimeoutError:
                    if retry == 2:
                        raise TimeoutError(f"Timeout after {timeout_seconds} seconds getting matchups for week {week} of {year} after 3 attempts")
                    logger.error(f"Timeout after {timeout_seconds} seconds getting matchups for week {week} of {year} (attempt {retry + 1}). Retrying...")
            
            for matchup in weekly_matchups:
                date_matchup = DateMatchup(
                    winner=matchup.home_team if matchup.home_score > matchup.away_score else matchup.away_team,
                    winner_score=matchup.home_score if matchup.home_score > matchup.away_score else matchup.away_score,
                    loser=matchup.away_team if matchup.home_score > matchup.away_score else matchup.home_team,
                    loser_score=matchup.away_score if matchup.home_score > matchup.away_score else matchup.home_score,
                    difference=round(abs(matchup.home_score - matchup.away_score), 2),
                    is_playoff=matchup.is_playoff,
                    matchup_type=matchup.matchup_type,
                    week=week,
                    year=year
                )
                self.matchups.append(date_matchup)

    def _get_activities(self, league: League, year: int, number_of_activities: int = 200, timeout_seconds: int = 30):
        """Collect recent league activities for a given year."""
        try:
            logger.info(f"Getting recent activities for year {year} with timeout {timeout_seconds} seconds")
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            activities = league.recent_activity(number_of_activities)
            signal.alarm(0)
            
        except TimeoutError:
            logger.error(f"Timeout after {timeout_seconds} seconds getting activities for year {year}")
            return
        except ESPNInvalidLeague as e:
            logger.error(f"Could not get activities for year {year}: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error getting activities for year {year}: {e}")
            return

        for activity in activities:
            date_activity = DateActivity(
                actions=activity.actions,
                date=activity.date,
                year=year,
                week=0 # Placeholder for week calculation if needed
            )
            self.activities.append(date_activity)

    def lowest_winning_point_totals(self, number_of_totals: int = 5):
        """Find the lowest point totals that resulted in a win."""
        sorted_matchups = sorted(self.matchups, key=lambda x: x.winner_score)
        top_results = sorted_matchups[:number_of_totals]
        
        self._write_to_file(f"\nTop {number_of_totals} lowest winning point totals:")
        self._write_to_file("=" * 50)
        for i, matchup in enumerate(top_results, 1):
            self._write_to_file(f"#{i}: {matchup.winner.owners[0].get('firstName')} {matchup.winner.owners[0].get('lastName')} won with only {matchup.winner_score} points against {matchup.loser.owners[0].get('firstName')} {matchup.loser.owners[0].get('lastName')} who scored {matchup.loser_score} in week {matchup.week} of {matchup.year}.")
        
        return top_results

    def highest_losing_point_total(self, number_of_totals: int = 5):
        """Find the highest point total that resulted in a loss."""
        sorted_matchups = sorted(self.matchups, key=lambda x: x.loser_score, reverse=True)
        top_results = sorted_matchups[:number_of_totals]

        self._write_to_file(f"\nTop {number_of_totals} highest losing point totals:")
        self._write_to_file("=" * 50)
        for i, matchup in enumerate(top_results, 1):
            self._write_to_file(f"#{i}: {matchup.loser.owners[0].get('firstName')} {matchup.loser.owners[0].get('lastName')} lost despite scoring {matchup.loser_score} points against {matchup.winner.owners[0].get('firstName')} {matchup.winner.owners[0].get('lastName')} who scored {matchup.winner_score} in week {matchup.week} of {matchup.year}.")

    def highest_score_all_time(self, number_of_totals: int = 5):
        """Find the highest score ever recorded in a matchup."""
        sorted_winner_matchups = sorted(self.matchups, key=lambda x: x.winner_score, reverse=True)[:number_of_totals]
        sorted_loser_matchups = sorted(self.matchups, key=lambda x: x.loser_score, reverse=True)[:number_of_totals]

        self._write_to_file(f"\nTop {number_of_totals} highest scores ever recorded:")
        self._write_to_file("=" * 50)
        winner_pointer = 0
        loser_pointer = 0
        for i in range(1, number_of_totals + 1):
            if sorted_loser_matchups[loser_pointer].loser_score > sorted_winner_matchups[winner_pointer].winner_score:
                matchup = sorted_loser_matchups[loser_pointer]
                self._write_to_file(f"#{i}: {matchup.loser.owners[0].get('firstName')} {matchup.loser.owners[0].get('lastName')} scored {matchup.loser_score} points in week {matchup.week} of {matchup.year}.")
                loser_pointer += 1
            else:
                matchup = sorted_winner_matchups[winner_pointer]
                self._write_to_file(f"#{i}: {matchup.winner.owners[0].get('firstName')} {matchup.winner.owners[0].get('lastName')} scored {matchup.winner_score} points in week {matchup.week} of {matchup.year}.")
                winner_pointer += 1

    def lowest_score_all_time(self, number_of_totals: int = 5):
        """Find the lowest score ever recorded in a matchup."""
        sorted_winner_matchups = sorted(self.matchups, key=lambda x: x.winner_score)[:number_of_totals]
        sorted_loser_matchups = sorted(self.matchups, key=lambda x: x.loser_score)[:number_of_totals]

        self._write_to_file(f"\nTop {number_of_totals} lowest scores ever recorded:")
        self._write_to_file("=" * 50)
        winner_pointer = 0
        loser_pointer = 0
        for i in range(1, number_of_totals + 1):
            if sorted_loser_matchups[loser_pointer].loser_score < sorted_winner_matchups[winner_pointer].winner_score:
                matchup = sorted_loser_matchups[loser_pointer]
                self._write_to_file(f"#{i}: {matchup.loser.owners[0].get('firstName')} {matchup.loser.owners[0].get('lastName')} scored {matchup.loser_score} points in week {matchup.week} of {matchup.year}.")
                loser_pointer += 1
            else:
                matchup = sorted_winner_matchups[winner_pointer]
                self._write_to_file(f"#{i}: {matchup.winner.owners[0].get('firstName')} {matchup.winner.owners[0].get('lastName')} scored {matchup.winner_score} points in week {matchup.week} of {matchup.year}.")
                winner_pointer += 1

    def closest_game(self, number_of_totals: int = 5):
        """Find the game with the smallest point differential."""
        sorted_matchups = sorted(self.matchups, key=lambda x: x.difference)
        top_results = sorted_matchups[:number_of_totals]

        self._write_to_file(f"\nTop {number_of_totals} closest games:")
        self._write_to_file("=" * 50)
        for i, matchup in enumerate(top_results, 1):
            self._write_to_file(f"#{i}: {matchup.winner.owners[0].get('firstName')} {matchup.winner.owners[0].get('lastName')} won with {matchup.winner_score} points against {matchup.loser.owners[0].get('firstName')} {matchup.loser.owners[0].get('lastName')} with {matchup.loser_score} points in week {matchup.week} of {matchup.year}. Difference: {matchup.difference} points.")

        return top_results

    def lifetime_top_scorers(self, number_of_teams: int = 5):
        """Find the teams with the highest lifetime total points scored."""
        team_points = {}
        for matchup in self.matchups:
            winner_coach = matchup.winner.owners[0].get('firstName') + " " + matchup.winner.owners[0].get('lastName')
            loser_coach = matchup.loser.owners[0].get('firstName') + " " + matchup.loser.owners[0].get('lastName')
            team_points[winner_coach] = matchup.winner_score + team_points.get(winner_coach, 0)
            team_points[loser_coach] = matchup.loser_score + team_points.get(loser_coach, 0)

        sorted_teams = sorted(team_points.items(), key=lambda x: x[1], reverse=True)[:number_of_teams]
        self._write_to_file(f"\nTop {number_of_teams} lifetime top scorers:")
        self._write_to_file("=" * 50)
        for i, (coach, points) in enumerate(sorted_teams, 1):
            self._write_to_file(f"#{i}: {coach} with {round(points, 2)} total points scored.")

    def season_points_allowed(self, start_year: int, end_year: int, number_of_teams: int = 5):
        """Calculate total points allowed per team per season."""
        points_allowed = {}

        for matchup in self.matchups:
            if matchup.year <= end_year and matchup.year >= start_year:
                winner_coach = matchup.winner.owners[0].get('firstName') + " " + matchup.winner.owners[0].get('lastName') + "," + str(matchup.year)
                loser_coach = matchup.loser.owners[0].get('firstName') + " " + matchup.loser.owners[0].get('lastName') + "," + str(matchup.year)
                points_allowed[winner_coach] = matchup.loser_score + points_allowed.get(winner_coach, 0)
                points_allowed[loser_coach] = matchup.winner_score + points_allowed.get(loser_coach, 0)

        highest_teams = sorted(points_allowed.items(), key=lambda x: x[1], reverse=True)[:number_of_teams]
        lowest_teams = sorted(points_allowed.items(), key=lambda x: x[1])[:number_of_teams]
        self._write_to_file(f"\nHighest season points allowed from {start_year} to {end_year}:")
        self._write_to_file("=" * 50)
        for i, (coach_year, points) in enumerate(highest_teams, 1):
            coach, year = coach_year.split(",")
            self._write_to_file(f"#{i}: {coach} in {year} allowed {round(points, 2)} points.")

        self._write_to_file(f"\nLowest season points allowed from {start_year} to {end_year}:")
        self._write_to_file("=" * 50)
        for i, (coach_year, points) in enumerate(lowest_teams, 1):
            coach, year = coach_year.split(",")
            self._write_to_file(f"#{i}: {coach} in {year} allowed only {round(points, 2)} points.")
