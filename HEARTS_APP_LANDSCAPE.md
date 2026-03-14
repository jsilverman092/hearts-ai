# Hearts App Landscape Notes

Last updated: 2026-03-14

## Scope

This note is a lightweight market scan of the current Hearts app landscape, with extra focus on NeuralPlay's `Hearts - Expert AI`.

It is not a full app-store census. The goal is narrower:

- understand how commercial Hearts apps position their bots
- identify which apps explicitly market "expert" or unusually strong AI
- identify which apps have real in-app strategic feedback systems such as hints, move suggestions, play checkers, or explanations
- extract product ideas that matter for `hearts-ai`

## Executive Summary

The current Hearts app market appears to split into three broad buckets:

1. Single-player, AI-first teaching apps.
2. Casual/mobile-first Hearts apps with "smart" or "adaptive" bots.
3. Online/social card platforms that include Hearts but are not primarily Hearts-AI products.

`Hearts - Expert AI` from NeuralPlay looks like one of the clearest AI-first products in the category. It stands out for four reasons:

- it explicitly brands itself around `Expert AI`
- it mixes strength claims with learning tools such as hints, play-checking, card counting, trick review, and replay
- NeuralPlay publicly says its card AIs are based on Monte Carlo simulation methods
- it appears to have one of the strongest in-app strategy-feedback toolsets in the category

The broader landscape is more mixed. Several competitors claim `smart`, `adaptive`, `challenging`, or `advanced` AI, but fewer pair that with detailed teaching/review tools. Fewer still appear to offer anything close to `play this card and here is what the AI would do instead` style strategic feedback.

My main product takeaway is that NeuralPlay is probably the closest commercial analogue to the direction of this repo's `heuristic_v3 + explanation/debug + future search bot` vision. MobilityWare, KARMAN, A-Star, AI Factory, Trickster, and GrassGames each cover adjacent parts of the space, but usually with less explicit `show your work` style guidance than NeuralPlay.

## NeuralPlay Deep Dive

### What NeuralPlay says it is

NeuralPlay's company `About Us` page says the company develops `challenging AIs for card games`, that those AIs are intended to both `challenge you and teach you the games`, and that their AIs are `based on Monte Carlo Simulation methods`, specifically to support many rule variants. The same page also explicitly invites feedback via `support@neuralplay.com`.

Sources:

- [NeuralPlay About Us](https://www.neuralplay.com/about.html)
- [NeuralPlay game portal](https://hearts.neuralplay.com/)

### Hearts - Expert AI positioning

On both the App Store and Google Play, `Hearts - Expert AI` is positioned as a single-player, offline-capable Hearts app that tries to serve both learners and stronger players.

The product page emphasizes:

- six AI levels
- real-time AI guidance when your move differs from the bot's
- hints
- built-in card counter
- trick-by-trick review
- replay hand
- detailed statistics
- extensive rule customization and preset variants such as Omnibus, Spot, Team Hearts, Hooligan, Pip, and Black Maria

This is notable because many Hearts apps offer hints or difficulty settings, but fewer combine:

- multi-level AI
- explicit move comparison against bot choices
- post-hand review
- broad rules customization

Sources:

- [Hearts - Expert AI on the App Store](https://apps.apple.com/us/app/hearts-expert-ai/id1536040860)
- [Hearts - Expert AI on Google Play](https://play.google.com/store/apps/details?id=com.neuralplay.android.hearts)

### Signals that NeuralPlay treats strategic guidance as part of the product

There are three useful signals here:

1. The app-store pages explicitly advertise real-time AI guidance when your move differs from the AI's.
2. The listing also calls out hints, trick review, replay, and card counting instead of limiting itself to generic difficulty-level language.
3. NeuralPlay's company positioning is explicitly `challenge you and teach you the games`, which matches a teaching/analysis product rather than a pure casual game app.

None of that proves the Hearts AI is elite. It does suggest NeuralPlay is trying to make the AI legible to the player, not just hard to beat.

Sources:

- [NeuralPlay About Us](https://www.neuralplay.com/about.html)
- [Hearts - Expert AI on Google Play](https://play.google.com/store/apps/details?id=com.neuralplay.android.hearts)
- [Hearts - Expert AI on the App Store](https://apps.apple.com/us/app/hearts-expert-ai/id1536040860)

### Best inference about the product

My inference from the official materials is:

- NeuralPlay is not just shipping a generic casual Hearts app
- it is trying to be a serious `practice + learn + customize` Hearts product
- its AI stack is likely rule-aware and sampling-heavy rather than purely handcrafted in the simple sense
- it may be the strongest commercial reference point for this repo's current medium-term product direction

That is still an inference. The official sources do not prove world-class Hearts strength, and they do not expose enough technical detail to verify how strong the top level really is.

## Broader Hearts App Landscape

### 1. NeuralPlay Hearts - Expert AI

Positioning:

- strongest explicit `expert AI` branding I found in the mobile Hearts space
- very clearly AI-first and learning-oriented

AI/literacy features:

- six AI levels
- hints
- AI guidance / play checker
- card counter
- trick review
- replay hand
- detailed stats

In-app strategic feedback:

- strongest explicit `AI guidance / play checker` style pitch in this scan
- hints
- move-comparison guidance when your play differs from the AI
- trick review and replay add post-move learning support

Why it matters:

- closest commercial analogue to our current direction

Sources:

- [App Store](https://apps.apple.com/us/app/hearts-expert-ai/id1536040860)
- [Google Play](https://play.google.com/store/apps/details?id=com.neuralplay.android.hearts)
- [NeuralPlay About Us](https://www.neuralplay.com/about.html)

### 2. AI Factory Hearts / Hearts Pro

Positioning:

- long-running single-player Hearts product line
- not branded as `Expert AI`, but explicitly markets many CPU opponents from `beginner to expert`

AI/literacy features:

- 18 CPU Hearts players of varying skill
- hints
- undo
- stats
- rules/help

In-app strategic feedback:

- hints are clearly advertised
- expert-tier CPU ladder is clearly advertised
- weaker evidence than NeuralPlay for explicit `compare your move to the AI's move` guidance

Why it matters:

- probably the clearest non-NeuralPlay example of a Hearts app explicitly selling bot strength tiers rather than just generic casual play

Sources:

- [Hearts Pro on Google Play](https://play.google.com/store/apps/details?id=uk.co.aifactory.hearts)
- [Hearts on Google Play](https://play.google.com/store/apps/details?id=uk.co.aifactory.heartsfree)
- [AI Factory contact page](https://www.aifactory.co.uk/AIF_Contact.htm)

### 3. Hearts+ by A-Star Software

Positioning:

- large, long-running multiplayer-plus-solo Hearts brand
- markets `Smart AI` and `challenging and competitive computer opponents`
- more mass-market and social than NeuralPlay

AI/literacy features:

- solo plus multiplayer
- smart AI opponents
- tutorial
- stats
- achievements

In-app strategic feedback:

- tutorial and smart-AI positioning
- weaker evidence for explicit per-play recommendation or explanation tooling

Why it matters:

- strong signal that a durable Hearts product can combine solo bots, multiplayer, stats, and frequent updates without centering explicit expert analysis

Sources:

- [Hearts+ on the App Store](https://apps.apple.com/us/app/hearts/id398890666)
- [A-Star Hearts+ Android page](https://www.astarsoftware.com/apps/hearts-android)
- [A-Star support page](https://astarsoftware.com/support)

### 4. Hearts by KARMAN Games

Positioning:

- Hearts app with both `really challenging computers` and online multiplayer
- less teaching-oriented than NeuralPlay, more traditional card-app positioning

AI/literacy features:

- challenging computers
- advanced statistics
- rules options
- online multiplayer

In-app strategic feedback:

- strong statistics and challenging-bot positioning
- weaker evidence for hint/checker/explanation tooling than NeuralPlay or MobilityWare

Why it matters:

- useful reference for the `strong bots + online play` market segment
- more of a competitive service app than a teaching/analysis app

Sources:

- [Hearts - Play online & offline on the App Store](https://apps.apple.com/us/app/hearts-play-online-offline/id1059473669)
- [Hearts on Google Play](https://play.google.com/store/apps/details?id=com.karmangames.hearts)

### 5. MobilityWare Hearts / Hearts NETFLIX

Positioning:

- mass-market casual Hearts with `adaptive` or `fair` AI language
- strongly focused on approachability, polish, hints, and scale

AI/literacy features:

- adaptive AI
- hints
- undo
- tutorial / advice
- offline play

In-app strategic feedback:

- hints
- tutorial/advice
- adaptive-AI framing
- looks stronger on onboarding guidance than on explicit `why this move` explanation

Why it matters:

- strong reference for mainstream consumer polish and onboarding
- weaker than NeuralPlay as a direct AI benchmark reference

Sources:

- [MobilityWare Hearts product page](https://www.mobilityware.com/hearts/)
- [MobilityWare support portal](https://www.mobilityware.com/support/)
- [MobilityWare unsolicited idea policy](https://www.mobilityware.com/unsolicited-idea-submission-policy/)
- [Google Play listing](https://play.google.com/store/apps/details?id=com.mobilityware.Hearts)
- [Hearts NETFLIX on the App Store](https://apps.apple.com/us/app/hearts-netflix/id6504045691)

### 6. Trickster Cards (Hearts included)

Positioning:

- social/multiplayer card platform rather than a Hearts-only AI product
- supports Hearts alongside several other trick-taking games

AI/literacy features:

- Hearts is available, but the product pitch is more about multiplayer, custom rules, chat, and cross-device play than about elite Hearts bots

In-app strategic feedback:

- weak evidence from official product pages for Hearts-specific move guidance or explanation tooling
- product is more social/multiplayer-first than AI-teaching-first

Why it matters:

- strongest visible feedback/community system in this scan
- useful reference if this repo later adds multiplayer, community features, or structured user feedback intake

Sources:

- [Trickster Cards App Store page](https://apps.apple.com/us/app/trickster-cards/id982267355)
- [Trickster Send Feedback](https://www.trickstercards.com/feedback/)
- [Trickster Help](https://www.trickstercards.com/home/help/)
- [Trickster About](https://www.trickstercards.com/about/)

### 7. GrassGames Hearts

Positioning:

- older-style premium/cross-platform Hearts product
- explicitly markets `intelligent computer opponents` plus network play

AI/literacy features:

- intelligent computer opponents
- multi-platform network play
- multiple variants

In-app strategic feedback:

- intelligent-opponent claim and variant support are clear
- I did not find strong official evidence of move-recommendation or explanation tooling

Why it matters:

- useful example of a more traditional desktop-style Hearts product where forums still matter

Sources:

- [GrassGames Hearts home](https://www.grassgames.com/hearts/)
- [GrassGames Hearts support](https://www.grassgames.com/hearts/support/)
- [GrassGames Hearts for iPad](https://apps.apple.com/us/app/grassgames-hearts-for-ipad/id1094989933)

## Which Apps Really Claim "Expert" Bots?

### Clearest explicit claims

- `NeuralPlay Hearts - Expert AI`
- `AI Factory Hearts / Hearts Pro` indirectly, via `beginner to expert` CPU tiers

### Strong-but-not-literal "expert" claims

- `Hearts+`: `Smart AI`, `challenging and competitive computer opponents`
- `KARMAN Hearts`: `really challenging computers`
- `MobilityWare Hearts`: `adaptive`, `fair`, `smart` AI
- `GrassGames Hearts`: `intelligent computer opponents`

Sources:

- [NeuralPlay Hearts](https://apps.apple.com/us/app/hearts-expert-ai/id1536040860)
- [AI Factory Hearts Pro](https://play.google.com/store/apps/details?id=uk.co.aifactory.hearts)
- [Hearts+](https://apps.apple.com/us/app/hearts/id398890666)
- [KARMAN Hearts](https://apps.apple.com/us/app/hearts-play-online-offline/id1059473669)
- [MobilityWare Hearts](https://www.mobilityware.com/hearts/)
- [GrassGames Hearts](https://www.grassgames.com/hearts/)

## Which Apps Have Real In-App Strategic Feedback Systems?

### Strongest evidence of move guidance / recommendation tooling

- `NeuralPlay`
  - explicit `AI guidance` / play-checker language
  - hints
  - trick review and replay
  - clearly the best match to the kind of per-play recommendation loop we just added

- `MobilityWare`
  - hints plus tutorial/advice
  - clearly some in-app teaching support, but less evidence of explicit move explanation

- `AI Factory`
  - hints and difficulty ladder
  - likely useful as a practice app, but weaker evidence than NeuralPlay for explicit explanatory feedback

### Mostly hints/tutorial/statistics rather than explanation

- `A-Star / Hearts+`
  - tutorial and smart-AI positioning
  - not much official evidence of `AI says play X because ...` style tooling

- `KARMAN`
  - challenging bots and stats
  - not much official evidence of per-play recommendations

- `GrassGames`
  - intelligent-opponent positioning
  - no strong official evidence of in-app move explanation tooling

- `Trickster`
  - strongest support/community loop in this scan
  - not a strong example of Hearts-specific strategic feedback

## Product Takeaways For This Repo

### 1. NeuralPlay is the closest commercial benchmark

If the question is `what existing app feels most adjacent to what we are trying to build`, the answer appears to be NeuralPlay's Hearts app.

Why:

- it treats Hearts as a strategy-learning product, not just a casual card app
- it pairs strong-AI marketing with move guidance and post-hand analysis
- it supports many variants, which lines up with NeuralPlay's stated Monte Carlo/rule-adaptive approach

### 2. There is still room for a more transparent bot

Several apps claim smart or challenging AI. Much fewer appear to expose a clear `why did the bot do that?` workflow.

That matters because one of this repo's explicit goals is helping a strong human player learn. A transparent heuristic bot and later transparent search bot could differentiate more on `inspectability` than on raw polish alone.

### 3. Strategic feedback is a meaningful product differentiator

The market has plenty of Hearts apps with bots, hints, or tutorials. It appears to have fewer apps that visibly center `the AI recommends this move` as part of the core learning loop.

That matters because this repo can differentiate not just on strength, but on transparent guidance:

- what the bot recommends
- why it recommends it
- where your move diverged
- later, how a stronger search bot disagrees with the heuristic bot

### 4. The market splits between learning and live service

There is a real product distinction between:

- `practice/analysis-first` apps like NeuralPlay
- `social/online` apps like Trickster, KARMAN, and Hearts+

That suggests this repo should stay clear on what it is trying to be:

- a strongest-bot lab
- a learning tool
- a consumer Hearts destination
- or some combination, phased over time

## Open Questions

These would be worth investigating later if we decide this market scan matters strategically:

- How strong is NeuralPlay's top Hearts AI in actual expert-player terms?
- Does NeuralPlay's Monte Carlo claim imply per-move sampling in Hearts, or is it mostly a rule-variant adaptation story?
- Which of these apps actually convert users because of bot strength versus polish and convenience?
- Are there any Hearts apps with truly robust move-explanation tooling beyond hints/checkers?

## Bottom Line

The commercial Hearts app space is active, but the most relevant products do not all compete on the same axis.

`NeuralPlay Hearts - Expert AI` looks like the strongest direct product comparison for this repo because it combines:

- explicit AI quality positioning
- learning support
- clear move-guidance features
- post-hand analysis
- customization depth

The main alternative reference points are:

- `Trickster` for community/service design
- `Hearts+` and `KARMAN` for online-plus-bot positioning
- `MobilityWare` for mainstream polish and onboarding
- `AI Factory` for explicit difficulty-tiered single-player bots

If the long-term goal is a Hearts app that helps strong players improve while also making the bot's reasoning inspectable, there still appears to be room to build something meaningfully differentiated.
