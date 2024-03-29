import requests
import pandas as pd
import matplotlib.pyplot as plt

#GLOBAL VARS
SWID = '{57B4B317-2F55-435D-9DF6-668437B00701}'
ESPN_S2 = 'AEBL7UeAj4QAcd4TPeQg8zCVRjKHWRAPJfMEWq6N7xRu617tqVNWACNQxFdqwYfVz%2FaRZqsayl5GI0bNn%2FoOIHo5Z62Nr0bRkyz7UogR3m28TK3dHtETUu%2B%2F0geIV6o0VjrXs6JpXhZzW2Bc%2Fcw%2FD7WYf%2Bfk2DC%2FrNTkhAm0cqLdJx2rEJkKvbsERCEkGsjh3hmXeiIn2kyIYKSo%2Fw4FUD2%2F6akIxhjbtQN4wQFkju9PgMvfKGXTcWDaFBne%2FvAbWHQpGYkEeWSW9idF6ZvCpJxPGXL%2BF3AojcCmzwMfQyDNbw%3D%3D'
FANTASY_LEAGUE = '1593617969'
GAME_SEASON = '2023'
GAME_WEEK = '1'

# positions
POSITION_CODES = {
    0: 'QB', 1: 'QB',
    2: 'RB', 3: 'RB',
    4: 'WR', 5: 'WR',
    6: 'TE', 7: 'TE',
    16: 'D/ST',
    17: 'K',
    20: 'Bench',
    21: 'IR',
    23: 'Flex'
}

# espn data
def grab_data(league, year, current_week, cookie_swid, cookie_espn):
    api_endpoint = f'https://fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league}'
    params = {'view': 'mMatchup', 'view': 'mMatchupScore', 'scoringPeriodId': current_week, 'matchupPeriodId': current_week}
    cookies = {"SWID": cookie_swid, "espn_s2": cookie_espn}
    response = requests.get(api_endpoint, params=params, cookies=cookies)
    return response.json()

# Create a lineup from data
def lineup_from_data(fetched_data, current_week):
    lineups = {}
    for team in fetched_data['teams']:
        team_lineup = []
        for entry in team['roster']['entries']:
            player_details = entry['playerPoolEntry']['player']
            player_name = player_details['fullName']
            slot_position = entry['lineupSlotId']
            lineup_position = POSITION_CODES[slot_position]
            
            actual_points, projected_points = 0, 0
            for stat in player_details['stats']:
                if stat['scoringPeriodId'] == current_week:
                    if stat['statSourceId'] == 0:
                        actual_points = stat['appliedTotal']
                    elif stat['statSourceId'] == 1:
                        projected_points = stat['appliedTotal']

            player_position = 'Unknown'
            for slot, position in POSITION_CODES.items():
                if slot in player_details['eligibleSlots']:
                    player_position = position
                    break

            team_lineup.append([player_name, slot_position, lineup_position, player_position, actual_points, projected_points])
        lineup_df = pd.DataFrame(team_lineup, columns=['Name', 'SlotID', 'Lineup', 'Position', 'Scored', 'Forecast'])
        lineups[team['id']] = lineup_df
    return lineups

def tally_scores(team_lineups, positions_order, ideal_structure):
    scores_sheet = {}
    for id, roster in team_lineups.items():
        points_tally = {'optimal': 0, 'estimated': 0, 'actual': 0}
        points_tally['actual'] = roster.query('Lineup not in ["Bench", "IR"]')['Scored'].sum()
        best_flex_score, best_flex_forecast = -100, -100
        for method, category in [('Scored', 'optimal'), ('Forecast', 'estimated')]:
            for pos, count in zip(positions_order, ideal_structure):
                position_scores = roster.query('Position == @pos').sort_values(by=method, ascending=False)
                actual_points = position_scores['Scored'].values
                forecast_points = position_scores['Forecast'].values

                points_tally[category] += actual_points[:count].sum()

                if pos in ['RB', 'WR', 'TE'] and len(actual_points) > count:
                    next_best = actual_points[count] if method == 'Scored' else forecast_points[count]
                    if next_best > best_flex_forecast:
                        best_flex_score = actual_points[count]
                        best_flex_forecast = next_best
            points_tally[category] += best_flex_score
        scores_sheet[id] = points_tally
    return scores_sheet

def get_team_names(league, year, current_week, cookie_swid, cookie_espn):
    endpoint = f'https://fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league}'
    params = {'view': 'mTeam', 'scoringPeriodId': current_week}
    cookies = {"SWID": cookie_swid, "espn_s2": cookie_espn}
    resp = requests.get(endpoint, params=params, cookies=cookies)
    data = resp.json()
    names = {team['id']: f"{team['location'].strip()} {team['nickname'].strip()}" for team in data['teams']}
    return names
def draw_the_week(week_data, score_data, the_week, team_names_dict, matchups=5):
    fig, ax = plt.subplots(figsize=(12, 8))
    match_height, match_gap = 5, 2
    team_positions, team_labels, bold_labels = [], [], []

    current_y_position = 0
    for match in week_data['schedule'][:matchups]:
        if 'away' in match and 'home' in match:
            away_id, home_id = match['away']['teamId'], match['home']['teamId']
            away_name, home_name = team_names_dict[away_id], team_names_dict[home_id]

            team_positions.extend([current_y_position, current_y_position + match_gap])
            team_labels.extend([away_name, home_name])
            bold_labels.append(1 if score_data[away_id]['actual'] > score_data[home_id]['actual'] else 0)
            bold_labels.append(1 if score_data[home_id]['actual'] > score_data[away_id]['actual'] else 0)

            for team_id in [away_id, home_id]:
                actual_points = score_data[team_id]['actual']
                optimal_points = score_data[team_id]['optimal']
                estimated_points = score_data[team_id]['estimated']

                ax.plot([actual_points, actual_points], [current_y_position - 1, current_y_position + 1], 'k-', alpha=0.75)
                ax.scatter([estimated_points], [current_y_position], c='w', s=200, edgecolor='g', label='Estimated' if current_y_position == 0 else "")
                ax.scatter([optimal_points], [current_y_position], c='b', s=100, alpha=0.2, label='Optimal' if current_y_position == 0 else "")

                current_y_position += match_height

    ax.set_yticks(team_positions)
    ax.set_yticklabels(team_labels)
    for label, tick in zip(bold_labels, ax.get_yticklabels()):
        if label: tick.set_weight("bold")
    ax.invert_yaxis()  # Ensures top matchup is at the top
    ax.legend(loc='upper right')
    ax.set_title(f'Week {the_week} Performance')
    plt.tight_layout()

    return fig, ax


positions = ['QB', 'RB', 'WR', 'Flex', 'TE', 'D/ST', 'K']
setup = [1, 2, 3, 1, 1, 1, 1]

data = grab_data(FANTASY_LEAGUE, GAME_SEASON, GAME_WEEK, SWID, ESPN_S2)
teams_lineup = lineup_from_data(data, GAME_WEEK)
scores = tally_scores(teams_lineup, positions, setup)
team_names = get_team_names(FANTASY_LEAGUE, GAME_SEASON, GAME_WEEK, SWID, ESPN_S2)

fig, ax = draw_the_week(data, scores, GAME_WEEK, team_names, matchups=5)
plt.show()