# Selection and uniqueness research

Research date: 2026-07-30.

## Requirements

The selected character had to be existing, recognizable, anime-style, legally
usable for a generated open-source derivative, connected to strong GitHub
interest, and absent from Codex pet repositories found in local and online
search. The project also needed a real function beyond installation, validation,
or a sprite preview.

## Candidate review

| Candidate | Popularity and GitHub fit | Rights result | Decision |
| --- | --- | --- | --- |
| Godette / Godot-chan | official Godot personification; Godot has a very large GitHub community | official design repository files are CC BY 4.0 | selected |
| Unity-chan | strong Unity developer recognition and popular GitHub shader projects | current official license forbids use of the character as AI image-generation input | rejected |
| Reimu / Cirno | extremely recognizable Touhou characters | fan-work and software distribution boundaries require more project-specific interpretation | rejected |
| Zundamon | popular Japanese character | multi-part character, voice, and usage terms add avoidable release complexity | rejected |
| Wikipe-tan | established CC-licensed personification | weaker direct developer-project heat than Godette | rejected |

Primary sources:

- [Godette article on the official Godot site](https://godotengine.org/article/godot-has-been-renamed-godette-engine/)
- [Godette reference directory at the pinned upstream commit](https://github.com/godotengine/godot-design/tree/7d12f300c377712028e9af6be01511b3e05a534c/godette)
- [godot-design repository license](https://github.com/godotengine/godot-design/blob/7d12f300c377712028e9af6be01511b3e05a534c/LICENSE)
- [Godot Engine repository](https://github.com/godotengine/godot)
- [Official Unity-chan license](https://unity-chan.com/contents/license_en/)

## Character uniqueness checks

The following GitHub repository/code searches returned no matching Godette
Codex v2 pet at research time:

- `"codex pet" godot-chan`
- `codex-pet godot`
- `Godette "Codex pet"`
- `Godette "spriteVersionNumber"`

The local workspace was also searched by directory, README, manifest, character
name, and feature keywords. Existing or in-progress pets included Baiyan,
Miaocui Jiao Cat, Feibi/Jiubi, Kiki, Pepper and Carrot, Kagamine Rin, Sakuya
Izayoi, Scales, and Takopi. No Godette pet was present before this repository.

## Product uniqueness and pivot

Initial online searches found no Codex-pet JSONL session renderer, so a small
deterministic fixture compiler was implemented. During development, a fresh
local read-only check found newly created Kagamine Rin and Takopi projects with
substantially similar session trace or replay features. Treating the stale
search result as final would have violated the non-duplication requirement.

The main product was therefore changed to PetDiff CI. Fresh GitHub searches
returned no relevant results for:

- `"Codex pet" "visual regression"`
- `"codex-pet" "pixel diff"`
- `"Codex pet" "GitHub Action" validator`
- `"spriteVersionNumber" diff Codex`

PetDiff compares two validated v2 packages cell by cell, measures pixel and
silhouette drift, enforces explicit budgets, and emits CI artifacts. The trace
code remains only as a deterministic animation fixture used by the release gate.

## Source integrity

Reference art is pinned, hashed, and retained under `artwork/references`. The
project does not depend on a mutable search-result image or an uncredited fan
upload. Generated derivative art is separately attributed and licensed under
CC BY 4.0.
