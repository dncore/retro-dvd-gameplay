# Data sources

- `catalog.json` — generated from the user's own ISO/ROM set (`G001`–`G300`). No ROM data
  is stored here, only paths, mapper/size metadata and display names.
- `dvd_names_tieba.txt` / `tieba_names.json` — the 300 Chinese menu names, transcribed
  by a Baidu Tieba user from the disc's menu:
  <https://tieba.baidu.com/p/2179922897>. Obvious hand-typing errors were corrected
  (e.g. 魂门罗 → 魂斗罗, 太空毁减者 → 太空毁灭者, 幸巴达 → 辛巴达).
- `dvd_names.raw.txt` / `dvd_names.json` — an earlier partial list (indices 1–80 and
  201–210) kept for provenance; the full Tieba list supersedes it.

The English titles used for cross-checking come from the BootlegGames Wiki article
[Super Game VCD 300](https://bootleggames.fandom.com/wiki/Super_Game_VCD_300) (CC-BY-SA).
Note that the wiki's "main menu" screenshot is a fan recreation, not a real capture, so
it was used only to check ordering and canonical game titles.

Game names are factual labels; no disc artwork, ROMs or ISO data are included in this
repository.
