---
title: V2-03 League Census
tags: [polysweeper, v2, research, leagues]
created: 2026-10-03
---

# V2-03 League census (Polymarket, last 7 days)

Back to [[V2-Home]] · Plan: [[V2-02-Research-Plan]]

Measured 2026-10-03 from Polymarket's public market data: finished matches that had a match-winner market.

- **117 leagues** had at least one finished match in the last 7 days.
- **About 749 matches a day** and **1115 match-winner markets a day** in total.
- The busiest are **not** the famous leagues: table tennis (Setka Cup), lower-tier tennis (ITF), CS2, ATP/WTA tennis and LoL dominate the count.
- Football counts 3 markets per match (home, draw, away); most other sports have 1.

## Top 40 leagues by matches per day

| # | League | Matches/day | Winner markets/day | Official result source |
|---|---|---|---|---|
| 1 | Setka Cup UA (M) (`setkameua`) | 142.9 | 142.9 | https://setkacup.com |
| 2 | ITF (`itf`) | 142.9 | 142.9 | https://www.itftennis.com/en/tournament-calendar/ |
| 3 | Setka Cup CZ (M) (`setkamecz`) | 53.3 | 53.3 | https://setkacup.com |
| 4 | CS2 (`cs2`) | 52.3 | 52.3 | https://hltv.org |
| 5 | ATP Tour (`atp`) | 44.0 | 44.0 | https://www.atptour.com/en/scores/current |
| 6 | Setka Cup MD (M) (`setkamemd`) | 39.3 | 39.3 | https://setkacup.com |
| 7 | WTA Tour (`wta`) | 25.3 | 25.3 | https://www.wtatennis.com/scores |
| 8 | LoL (`lol`) | 15.7 | 15.7 | https://liquipedia.net/leagueoflegends/Main_Page |
| 9 | MODUS Super Series (`modus`) | 14.9 | 14.9 | https://modussuperseries.com/ |
| 10 | College Football (`cfb`) | 14.7 | 14.7 | https://www.ncaa.com/ |
| 11 | ATP Doubles (`atp-doubles`) | 14.0 | 14.0 | https://www.atptour.com/en/scores/current |
| 12 | MLB (`mlb`) | 13.3 | 13.3 | https://www.mlb.com/ |
| 13 | WTA Doubles (`wta-doubles`) | 11.0 | 11.0 | https://www.wtatennis.com/scores |
| 14 | UEFA Nations League (`unl`) | 7.7 | 23.1 | https://www.uefa.com/uefanationsleague/ |
| 15 | Rainbow Six Siege (`r6siege`) | 7.4 | 7.4 | https://liquipedia.net/rainbowsix/Main_Page |
| 16 | Dota 2 (`dota2`) | 6.3 | 6.3 | https://www.liquipedia.net/dota2/Main_Page |
| 17 | Mobile Legends: Bang Bang (`mlbb`) | 6.1 | 6.1 | https://liquipedia.net/mobilelegends/Main_Page |
| 18 | Honor of Kings (`hok`) | 5.7 | 5.7 | https://liquipedia.net/honorofkings/Main_Page |
| 19 | International (`crint`) | 5.1 | 5.4 | https://www.icc-cricket.com/ |
| 20 | CONCACAF Nations League (`conl`) | 4.7 | 14.1 | https://www.concacaf.com/ |
| 21 | NPB (`npb`) | 4.6 | 4.6 | https://npb.jp/ |
| 22 | Setka Cup UA (W) (`setkawoua`) | 4.4 | 4.4 | https://setkacup.com |
| 23 | KHL (`khl`) | 4.3 | 4.3 | https://en.khl.ru/calendar/ |
| 24 | NHL (`nhl`) | 4.1 | 4.1 | https://www.nhl.com/ |
| 25 | Davis Cup (`daviscup`) | 3.9 | 3.9 | https://www.daviscup.com/ |
| 26 | FIFA Friendlies (`fif`) | 3.7 | 11.1 | https://www.fifa.com/en |
| 27 | National League (`enl`) | 3.4 | 10.3 | https://www.thenationalleague.org.uk/ |
| 28 | Africa Cup of Nations Qualifiers (`afcq`) | 3.3 | 9.9 | https://www.cafonline.com/ |
| 29 | National League (`snhl`) | 2.9 | 2.9 | https://www.nationalleague.ch/ |
| 30 | Czech Extraliga (`cehl`) | 2.9 | 2.9 | https://www.hokej.cz/tipsport-extraliga |
| 31 | Liiga (`liiga`) | 2.7 | 2.7 | https://liiga.fi/en |
| 32 | EuroLeague (`euroleague`) | 2.7 | 2.7 | https://www.euroleaguebasketball.net/euroleague/ |
| 33 | Primera Nacional (`argpn`) | 2.6 | 7.7 | https://www.afa.com.ar/ |
| 34 | Valorant (`val`) | 2.6 | 2.6 | https://liquipedia.net/valorant/Main_Page |
| 35 | SHL (`shl`) | 2.4 | 2.4 | https://www.eliteprospects.com/league/shl |
| 36 | MLS (`mls`) | 2.3 | 6.9 | https://www.mls.com/ |
| 37 | NFL (`nfl`) | 2.1 | 2.1 | https://www.nfl.com/ |
| 38 | USL Championship (`uslc`) | 2.0 | 6.0 | https://www.uslchampionship.com/ |
| 39 | DEL (`dehl`) | 2.0 | 2.0 | https://www.penny-del.org/en/del/schedule-and-results.html |
| 40 | Basketball Bundesliga (`bkbbl`) | 2.0 | 2.0 | https://www.easycredit-bbl.de/en/ |

## What this means for V2

1. **Coverage beats depth.** A bot covering tennis (ITF, ATP, WTA, doubles), table tennis and the big esports would see hundreds of finished matches a day; 68 leagues is very plausible for a late-band sweeper.
2. **Each sport needs its own finality rules** before it can be used: tennis retirements and walkovers, table-tennis match formats, esports series, baseball/hockey overtime.
3. **Next:** check which of these leagues actually show sellers at 0.995-0.999 after the end (needs the public trades data and our shadow logs), and which have a free result source.

Full list: `code/data/league_census.json` (all leagues with matches in the window).
