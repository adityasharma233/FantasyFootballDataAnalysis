import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

swid='{57B4B317-2F55-435D-9DF6-668437B00701}'

espn='AEBL7UeAj4QAcd4TPeQg8zCVRjKHWRAPJfMEWq6N7xRu617tqVNWACNQxFdqwYfVz%2FaRZqsayl5GI0bNn%2FoOIHo5Z62Nr0bRkyz7UogR3m28TK3dHtETUu%2B%2F0geIV6o0VjrXs6JpXhZzW2Bc%2Fcw%2FD7WYf%2Bfk2DC%2FrNTkhAm0cqLdJx2rEJkKvbsERCEkGsjh3hmXeiIn2kyIYKSo%2Fw4FUD2%2F6akIxhjbtQN4wQFkju9PgMvfKGXTcWDaFBne%2FvAbWHQpGYkEeWSW9idF6ZvCpJxPGXL%2BF3AojcCmzwMfQyDNbw%3D%3D'

league_id = '1593617969'

season = '2023'
week = 1

slotcodes = {
    0 : 'QB', 1 : 'QB',
    2 : 'RB', 3 : 'RB',
    4 : 'WR', 5 : 'WR',
    6 : 'TE', 7 : 'TE',
    16: 'D/ST',
    17: 'K',
    20: 'Bench',
    21: 'IR',
    23: 'Flex'
}

url = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{}/segments/0/leagues/{}?scoringPeriodId=1&view=mBoxscore&view=mMatchupScore'.format(season,league_id)

r = requests.get(url, 
                 params={'scoringPeriodId': week}, 
                 cookies={"SWID": swid, "espn": espn})

espn_raw_data = r.json()


def get_matchups(league_id, season, week, swid='', espn=''):

    
    url = 'https://fantasy.espn.com/apis/v3/games/ffl/seasons/' + \
      str(season) + '/segments/0/leagues/' + str(league_id)

    r = requests.get(url + '?view=mMatchup&view=mMatchupScore',
                     params={'scoringPeriodId': week, 'matchupPeriodId': week},
                     cookies={"SWID": swid, "espn_s2": espn})
    return r.json()

def get_slates(json):
    
    slates = {}

    for team in d['teams']:
        slate = []
        for p in team['roster']['entries']:
            # get name
            name  = p['playerPoolEntry']['player']['fullName']

            # get actual lineup slot
            slotid = p['lineupSlotId']
            slot = slotcodes[slotid]

            # get projected and actual scores
            act, proj = 0, 0
            for stat in p['playerPoolEntry']['player']['stats']:
                if stat['scoringPeriodId'] != week:
                    continue
                if stat['statSourceId'] == 0:
                    act = stat['appliedTotal']
                elif stat['statSourceId'] == 1:
                    proj = stat['appliedTotal']
                else:
                    print('Error')

            # get type of player
            pos = 'Unk'
            ess = p['playerPoolEntry']['player']['eligibleSlots']
            if 0 in ess: pos = 'QB'
            elif 2 in ess: pos = 'RB'
            elif 4 in ess: pos = 'WR'
            elif 6 in ess: pos = 'TE'
            elif 16 in ess: pos = 'D/ST'
            elif 17 in ess: pos = 'K'

            slate.append([name, slotid, slot, pos, act, proj])

        slate = pd.DataFrame(slate, columns=['Name', 'SlotID', 'Slot', 'Pos', 'Actual', 'Proj'])
        slates[team['id']] = slate

    return slates

def compute_pts(slates, posns, struc):
   
    
    data = {}
    for tmid, slate in slates.items():
        pts = {'opts': 0, 'epts': 0, 'apts': 0}

        pts['apts'] = slate.query('Slot not in ["Bench", "IR"]').filter(['Actual']).sum().values[0]

        for method, cat in [('Actual', 'opts'), ('Proj', 'epts')]:
            actflex = -100  # actual pts scored by flex
            proflex = -100  # "proj" pts scored by flex
            for pos, num in zip(posns, struc):
                # actual points, sorted by either actual or proj outcome
                t = slate.query('Pos == @pos').sort_values(by=method, ascending=False).filter(['Actual']).values[:,0]

                # projected points, sorted by either actual or proj outcome
                t2 = slate.query('Pos == @pos').sort_values(by=method, ascending=False).filter(['Proj']).values[:,0]

                # sum up points
                pts[cat] += t[:num].sum()

                # set the next best as flex
                if pos in ['RB', 'WR', 'TE'] and len(t) > num:
                    fn = t[num] if method=='Actual' else t2[num]
                    if fn > proflex:
                        actflex = t[num]
                        proflex = fn

            pts[cat] += actflex
        
        data[tmid] = pts
        
    return data

def get_teamnames(league_id, season, week, swid='', espn=''):
    url = 'https://fantasy.espn.com/apis/v3/games/ffl/seasons/' + \
      str(season) + '/segments/0/leagues/' + str(league_id)
    
    r = requests.get(url + '?view=mTeam',
                  params={'scoringPeriodId': week},
                  cookies={"SWID": swid, "espn_s2": espn})
    d = r.json()
    
    tm_names = {tm['id']: tm['location'].strip() + ' ' + tm['nickname'].strip() \
                for tm in d['teams']}
    
    return tm_names

def plot_week(d, data, week, tm_names, nummatchups=5, 
              minx=70, maxx=200, legend=4):
    fig, ax = plt.subplots(1,1, figsize=(12,8))

    dif, offset = 5, 2
    
    tmlist, tmticks, tmbold = [], [], []

    cury = 0
    for g in d['schedule'][:nummatchups]:
        aid, anm = -1, ''
        hid, hnm = -1, ''
        try:
            aid = g['away']['teamId']
            anm = tm_names[aid]
            hid = g['home']['teamId']
            hnm = tm_names[hid]
        except:
            continue

        tmlist.append(anm)
        tmlist.append(hnm)

        if data[aid]['apts'] > data[hid]['apts']:
            tmbold.extend([1,0])
        else:
            tmbold.extend([0,1])

        for pts in [data[aid], data[hid]]:
            h = 1 if (pts['opts']-offset) > pts['apts'] else 0
            tmticks.append(cury)
            ax.plot([minx, maxx], [cury, cury], 'k--', linewidth=1, alpha=0.1)
            ax.plot([pts['apts'], pts['opts']-offset*h], [cury, cury], 'k-')
            ax.scatter(pts['epts'], cury, c='w', s=200, marker='o', edgecolor='g')
            ax.scatter(pts['apts'], cury, c='k', s=100)

            if pts['opts'] == pts['apts']:
                ax.scatter(pts['opts'], cury, c='w', s=25)
                ax.scatter(pts['opts'], cury, c='b', s=25, alpha=0.2)
            else:
                ax.scatter(pts['opts'], cury, c='b', s=100, alpha=0.2)

            cury += dif

        cury += 2*dif

    ax.set(yticks=tmticks,
           yticklabels=tmlist)
    for k, tick in enumerate(ax.yaxis.get_major_ticks()):
        if tmbold[k] == 1:
            tick.label1.set_fontweight('bold')

    ax.scatter([],[], c='k', s=100, label='Actual')
    ax.scatter([],[], c='w', s=200, marker='o', edgecolor='g', label='ESPN')
    ax.scatter([],[], c='b', s=100, alpha=0.2, label='Best Possible')
    ax.legend(loc=legend, borderaxespad=2, borderpad=1, labelspacing=1.5, 
              shadow=True, fontsize=12)

    ax.set(title='Week %d' % week)

    return ax

posns = ['QB', 'RB', 'WR', 'Flex', 'TE', 'D/ST', 'K']
struc = [1,2,3,1,1,1,1]


d      = get_matchups(league_id, season, week, swid=swid, espn=espn)
slates = get_slates(d)
wdata  = compute_pts(slates, posns, struc)
tms    = get_teamnames(league_id, season, week, swid=swid, espn=espn)

tms = {
    0:'a',
    1: 'b',
    2: 'c',
    3: 'd',
    4: 'e',
    5: 'f',
    6: 'Team Adi',
    7: 'Team 3',
    8: 'Shake it Goff',
    9: 'a^2 + b^2 = c^hawks',
    10: 'Kittle',
    11:'Mixon',
    12: 'the mustard',
    13: 'z',
    14: 'y',
    15: 'n'
}

ax = plot_week(d, wdata, week, tms, nummatchups=5)
plt.show()
