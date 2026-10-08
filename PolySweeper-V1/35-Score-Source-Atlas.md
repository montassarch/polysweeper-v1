---
title: Score-Source Atlas (all Polymarket sports + esports)
tags: [polysweeper, research, sources, scores]
created: 2026-10-08
---

# Score-Source Atlas

Back to [[V1-Home]] · Task list: [[24-Task-List]] · Research: [[R-2026-10-08]]

Owner request 2026-10-08: list every Polymarket sports and esports league, find each league's resolution source,
test whether a program can read scores from it, and find alternatives (any country) where it can't.
Read-only research from the laptop. Scripts: `lab/source_atlas.py` (leagues + source probe), `lab/source_coverage.py`
(match-by-match coverage). Data: `lab/results/source-atlas-leagues.json`, `source-atlas-sources.json`,
`source-coverage.json`.

## Headline numbers (8 Oct 2026)

- Polymarket lists **475 leagues** (Gamma `/sports`), with about **260 different resolution websites**.
- **172 leagues** have matches in the next 7 days (about 6,450 matches, about $15.9M volume). The rest are
  off-season or dead.
- The resolution **home page opens** for 129 of the 172 active leagues. Only **34** have the page data built in
  (Next.js/Nuxt) in a form a program can read easily. Most official league sites load scores with JavaScript from
  a hidden API, so "the page opens" is not "we can read scores".
- **Match-by-match test (3,006 Polymarket matches in the next 48 h):** 365Scores found 1,780, LiveScore 1,735,
  bo3.gg 70, LoL Esports 7. **At least one free source: 1,982 of 3,006 (66%).** Most of the misses are the sports in
  "Gaps" below, plus football leagues where 1-6 matches per league are extra Polymarket events (not real misses).
- Trap: 9 leagues (Egypt, Romania, Colombia, Brazil B, Morocco, Czechia, Peru, Bolivia, Chile 1) show a placeholder
  league-level source (LaLiga Supercopa). The **real source is on each event** (`resolutionSource`, e.g. efa.com.eg,
  lpf.ro). Scripts must read the event field, not the league field.

## By sport: resolution source, can we read it, best free alternative

| Sport (active leagues) | Polymarket's resolution source | Readable by a program? | Best free sources (tested) | Coverage measured |
|---|---|---|---|---|
| **Football**, about 100 leagues (EPL, LaLiga, Serie A, Bundesliga, Ligue 1, MLS, EFL, Saudi, J/K League, S. America ...) | Official league / FA sites (premierleague.com, laliga.com, uefa.com, cbf.com.br, spl.com.sa ...) | Mixed: uefa.com timed out; some 403 (football.ch, football.org.il, legaserieb.it); most open but JS-loaded | **365Scores**, **LiveScore** (both about 85-100% of real matches per league), **ESPN** (219 soccer leagues, already used by the bot), Kooora/Yallakora/FilGoal (Arabic) | Strong |
| **US: NFL, CFB, NBA, NHL, MLB, WNBA, AHL, CFL** | nfl.com, ncaa.com, nba.com (403), nhl.com, mlb.com | Official APIs: NHL `api-web.nhle.com`, MLB `statsapi.mlb.com`, NBA `cdn.nba.com` live JSON; ESPN for NFL/CFB | ESPN, 365Scores, LiveScore (no CFB/NFL/MLB on LiveScore) | Full |
| **Tennis ATP/WTA** | atptour.com, wtatennis.com | Open, JS-loaded | ESPN (in use, ~140 s ahead of Polymarket), 365Scores, LiveScore | 100% ATP/WTA singles |
| **Tennis ITF** (50 matches/2 days) | itftennis.com | **Blocked** (Incapsula) | **Flashscore** lists ITF (54 ITF events today); not on 365/LiveScore | Gap: only Flashscore |
| **Table tennis: Setka Cup** (UA/MD/CZ, about 170 matches/2 days, tiny volume) | setkacup.com | **Yes: official JSON** `tabletennis.setkacup.com/api/Matches/widget/en` (live, set scores, winner) | The source itself | Direct |
| Table tennis: TT Cup / Czech Liga Pro | tt-cup.com | Opens (SSL quirk only) | Flashscore (partly) | Not measured |
| **Cricket** (Tests, internationals, Ranji, Sheffield Shield, Legends) | espncricinfo.com (65 leagues), icc-cricket.com, bcci.tv | **ESPNcricinfo blocked** (403 site and API) | LiveScore (21 of 50), Flashscore, Cricbuzz page (HTML, its API blocked) | Partial (about 40%) |
| **Ice hockey Europe**: KHL, SHL, Liiga, DEL, Czech, Swiss | en.khl.ru, eliteprospects.com (403), liiga.fi, penny-del.org | **Liiga official JSON API works**; SHL API exists (needs right ids) | 365Scores (KHL 12/12), LiveScore (SHL, Liiga, DEL, Czech, Swiss) | Good |
| **Basketball** non-US: EuroLeague, ACB, BBL, Japan B.League, KBL, NBL, Turkey, VTB ... | euroleaguebasketball.net (429), acb.com, bleague.jp (503) ... | Mixed | 365Scores + LiveScore (about 90-100%) | Good |
| **Baseball** KBO, NPB, CPBL | koreabaseball.com, npb.jp, cpbl.com.tw | Pages open (Korean/Japanese HTML) | Flashscore (NPB); KBO/CPBL no aggregator hit | **Gap** |
| **Rugby** (URC, Top 14, Premiership), AFL/AFLW | unitedrugby.com, lnr.fr (404), premiershiprugby.com, afl.com.au | Partly | **ESPN rugby + AFL scoreboards work** (25 rugby leagues) | Gap on 365/LiveScore; ESPN not yet matched |
| **Handball** (EHF CL, Bundesliga, LNH, ASOBAL, Danish) | ehfcl.eurohandball.com, daikin-hbl.de ... | Mostly open | 365Scores (most), Flashscore | Partial |
| **Darts** (PDC, MODUS) | pdc.tv, modussuperseries.com | pdc.tv opens (1.2 MB page) | **Flashscore lists MODUS Super Series** | Gap on 365/LiveScore |
| **Pickleball** (PPA, MLP) | ppatour.com | Redirects; not tested deeper | None found yet | **Gap** |
| UFC, boxing, Power Slap | ufc.com, espn.com/boxing | ufc.com opens | ESPN MMA (48 leagues) | Not matched |
| Golf, F1, NASCAR, cycling | pgatour.com, formula1.com, nascar.com, uci.org | Outright winner markets, not head-to-head matches | ESPN golf/racing, Flashscore | Not relevant to sweeping matches |

### Esports

| Game | Polymarket's resolution source | Readable? | Best free sources (tested) |
|---|---|---|---|
| **CS2** (78 matches/2 days, biggest esports volume) | hltv.org | **Blocked** (Cloudflare 403) | **bo3.gg JSON** (70 of 78 found, 90%; live test running: `lab/cs2_end_race.py`), Liquipedia API |
| **Dota 2** | liquipedia.net | Page 403, **API works** with a proper app name (rate limit about 1 page per 30 s) | **OpenDota** (in use), Steam `GetLiveGames`, **bo3.gg** (discipline 4), Flashscore (top events) |
| **LoL** | liquipedia.net | API as above | **LoL Esports official API** (7 of 7), **bo3.gg** (discipline 3) |
| **Valorant** | liquipedia.net | API as above | **bo3.gg** (discipline 2), **vlr.gg** (HTML, 28 matches listed) |
| **Rainbow Six** | liquipedia.net | API as above | **bo3.gg** (discipline 7) |
| **Mobile Legends** | liquipedia.net | API as above | **bo3.gg** (discipline 8) |
| Overwatch, Honor of Kings, CoD, PUBG, StarCraft, Rocket League | liquipedia.net | API as above | Liquipedia only (slow) |

(The 48 h test matched bo3.gg only for CS2: the script read bo3.gg without a game filter, so the other games were
crowded out, and bo3.gg adds suffixes like "-1", "-lol", "-dota2" to team names. bo3.gg has all 6 games (checked
by game id); per-game matching is the next fix.)

## Sources by country (what answers, what blocks)

- **Works, free, no key:** 365Scores (Israel), LiveScore (UK), Flashscore (Czech; slower, #20), ESPN (USA; rate
  limit, see below), bo3.gg (esports), vlr.gg, LoL Esports (Riot), OpenDota, NHL/MLB/NBA official, Liiga
  (Finland), Setka Cup (Ukraine), Kooora (Qatar), Yallakora, FilGoal, Btolat (Egypt), beIN (Qatar), SPL (Saudi),
  Liquipedia API (slow), Cricbuzz HTML (India, page only).
- **Blocked from the laptop:** Sofascore (Croatia), HLTV (Denmark), FotMob (Norway, signed header), ESPNcricinfo
  (India/US), ITF, Elbotola (Morocco), Dongqiudi (China), NBA.com site (the cdn JSON works), EuroLeague site (429).
- **ESPN warning:** a fast burst (12 parallel requests) got the laptop **temporarily refused (403)** on 8 Oct.
  The live bot uses ESPN from the same machine. Any ESPN study must go 1 request per second at most.

## What this means for the bot (honest)

- **Second-source coverage is good where the money is.** Big football, US sports, ATP/WTA, KHL and EuroLeague all
  have 2-3 free sources besides Polymarket's own score.
- **CS2 now has a second source (bo3.gg).** It was our weakest spot (3 of 8 price-only losses). Speed is being
  measured.
- **Real gaps:** ITF tennis, cricket, KBO/CPBL, pickleball, rugby/AFL (ESPN only), darts, and Overwatch/HoK/CoD.
  These are mostly low-volume, except cricket (65 leagues).
- **Coverage is not speed.** None of this shows a source is faster than Polymarket's own score. Only the
  end-race tests show that (tennis: ESPN about 140 s ahead; CS2: running). A source is useful as a safety check
  even when it is not faster.
- Unofficial endpoints (365Scores, LiveScore, bo3.gg, Setka widget) can change or block without notice. Terms of
  use not yet read.

## Next steps (proposed)

1. Fix bo3.gg matching per game (Dota 2, LoL, Valorant, R6, MLBB) and re-run coverage.
2. A polite ESPN mapping pass (1 request/s) for rugby, AFL, MMA and smaller football leagues.
3. An end-race speed test for 365Scores and LiveScore on football and basketball (like `cs2_end_race.py`).
4. Cricket: test Cricbuzz page data and LiveScore cricket live feed.
5. Read the terms of use for the sources we would rely on.
