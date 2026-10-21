# Changelog

## 0.1.0 (2026-10-21)


### Features

* account and data deletion ([#65](https://github.com/felixhaegele/fitfinder/issues/65)) ([91a2882](https://github.com/felixhaegele/fitfinder/commit/91a2882689c4228ee3d8dc945a79019e5d760374))
* browse and search shoes by fit ([#96](https://github.com/felixhaegele/fitfinder/issues/96)) ([06d64a3](https://github.com/felixhaegele/fitfinder/commit/06d64a3e90cf85c655f094225785de4e7917a66c))
* core schema migrations with RLS ([#40](https://github.com/felixhaegele/fitfinder/issues/40)) ([f177342](https://github.com/felixhaegele/fitfinder/commit/f1773425583d1d14fed17ef9f44f8987a58a3d75))
* cross-device magic links (token-hash flow) ([#71](https://github.com/felixhaegele/fitfinder/issues/71)) ([6d2195e](https://github.com/felixhaegele/fitfinder/commit/6d2195ed25dfafe5fae7ba4ec67c20f8dc6562ad))
* diagonal A4 insole template PDF from shared geometry JSON ([#47](https://github.com/felixhaegele/fitfinder/issues/47)) ([a5f8515](https://github.com/felixhaegele/fitfinder/commit/a5f85151854d660f973b51d7eea1001dc70b3016))
* email magic-link auth in web ([#48](https://github.com/felixhaegele/fitfinder/issues/48)) ([e620ac5](https://github.com/felixhaegele/fitfinder/commit/e620ac5a82734974a9f51dab2230354b24803a0c))
* hello world end to end (web, worker, CI) ([#38](https://github.com/felixhaegele/fitfinder/issues/38)) ([a475846](https://github.com/felixhaegele/fitfinder/commit/a475846b431f61760ef8ed18bfdf8359e465d7a0))
* insole measurements in mm ([#80](https://github.com/felixhaegele/fitfinder/issues/80)) ([5934b8f](https://github.com/felixhaegele/fitfinder/commit/5934b8f0e82da60a99d6ca74dfb92674e0f4da87))
* landing page flow and privacy page ([#101](https://github.com/felixhaegele/fitfinder/issues/101)) ([4c82ada](https://github.com/felixhaegele/fitfinder/commit/4c82ada6ba6e911aaeb216b67636cc3c3f12dfe7))
* marker detection and homography warp ([#58](https://github.com/felixhaegele/fitfinder/issues/58)) ([493c089](https://github.com/felixhaegele/fitfinder/commit/493c0896afd23268374e53046886dd6ca9378f00))
* measure CLI with debug overlay ([#99](https://github.com/felixhaegele/fitfinder/issues/99)) ([f00c967](https://github.com/felixhaegele/fitfinder/commit/f00c967284009dd50728616241eb0cdde15a4d2d))
* pgmq submissions queue with enqueue trigger ([#43](https://github.com/felixhaegele/fitfinder/issues/43)) ([a07da7c](https://github.com/felixhaegele/fitfinder/commit/a07da7c9b50cd1d7f6f724f6d8ebec29301df3c5))
* printable template download on the website ([#97](https://github.com/felixhaegele/fitfinder/issues/97)) ([82dc70f](https://github.com/felixhaegele/fitfinder/commit/82dc70f6ac53c13a893971d454fd6f18c4e7735a))
* private insoles storage bucket with policies ([#41](https://github.com/felixhaegele/fitfinder/issues/41)) ([4f58ce4](https://github.com/felixhaegele/fitfinder/commit/4f58ce4cecca8a92b8fbf44fdc8e89a171c6d4e8))
* record insole condition (new/used) on submissions ([#57](https://github.com/felixhaegele/fitfinder/issues/57)) ([640ad56](https://github.com/felixhaegele/fitfinder/commit/640ad5626080dca9a0a753cd45287a62016c93f7))
* rule-based foot-shape classifier v1 ([#81](https://github.com/felixhaegele/fitfinder/issues/81)) ([0efd597](https://github.com/felixhaegele/fitfinder/commit/0efd597ddc76d93e1bfbbad7d3314c600d79dd0f))
* show toe shape on the status page ([#88](https://github.com/felixhaegele/fitfinder/issues/88)) ([a38bf00](https://github.com/felixhaegele/fitfinder/commit/a38bf0062425e3053d738e5ccd1da700f98c3441))
* store insole outline and toe shape ([#73](https://github.com/felixhaegele/fitfinder/issues/73)) ([6e89341](https://github.com/felixhaegele/fitfinder/commit/6e89341af6a1b6ab60a651e471d4dafcb7bf11e3))
* submission status and results pages ([#59](https://github.com/felixhaegele/fitfinder/issues/59)) ([9af436f](https://github.com/felixhaegele/fitfinder/commit/9af436fb2674f09f63deaf237874f85baa382069))
* upload form with consent and EXIF stripping ([#51](https://github.com/felixhaegele/fitfinder/issues/51)) ([67f6658](https://github.com/felixhaegele/fitfinder/commit/67f6658a0563f41a297393b50a55da9de5da174f))
* wire measurements and classification into the queue worker ([#85](https://github.com/felixhaegele/fitfinder/issues/85)) ([6367de9](https://github.com/felixhaegele/fitfinder/commit/6367de946b10b8b8fcccd352b044a4b6c8e99966))
* worker consumes queue and writes results ([#78](https://github.com/felixhaegele/fitfinder/issues/78)) ([b8f2bfe](https://github.com/felixhaegele/fitfinder/commit/b8f2bfe42f5cef31092f6034e9cca5b43001c8b1))


### Bug Fixes

* **ci:** log in to hosted databases via the access token, not a password ([#90](https://github.com/felixhaegele/fitfinder/issues/90)) ([7d053a8](https://github.com/felixhaegele/fitfinder/commit/7d053a85ede77eb04097a48b78c772905221de4f))
* delete both photos when a single submission is deleted ([#100](https://github.com/felixhaegele/fitfinder/issues/100)) ([ee835a9](https://github.com/felixhaegele/fitfinder/commit/ee835a9f2dc968d6f2d1f367a123ca7673b63bd6))
* reject unmeasurable insoles with a reason instead of retrying ([#98](https://github.com/felixhaegele/fitfinder/issues/98)) ([2c400a6](https://github.com/felixhaegele/fitfinder/commit/2c400a6b07b0e8b209d6984f07f65b4b09f3f248))


### Documentation

* capture environments, security model and decisions ([#79](https://github.com/felixhaegele/fitfinder/issues/79)) ([3d83145](https://github.com/felixhaegele/fitfinder/commit/3d8314502105233b62fd34808400773cd3b8a33c))
* conventions for parallel Claude sessions ([#50](https://github.com/felixhaegele/fitfinder/issues/50)) ([7a85939](https://github.com/felixhaegele/fitfinder/commit/7a85939a6dd815f8b102e18d887a6a097f0dbb73))


### CI/CD

* deploy web to Vercel with per-PR previews ([#67](https://github.com/felixhaegele/fitfinder/issues/67)) ([1cb7f3b](https://github.com/felixhaegele/fitfinder/commit/1cb7f3bd60a1d2df20b915a10aba17aea130a5be))
* exclude e2e-tested glue code from Sonar coverage ([#64](https://github.com/felixhaegele/fitfinder/issues/64)) ([c63d04b](https://github.com/felixhaegele/fitfinder/commit/c63d04b8dd0125255d62f056bbfa4b01e66d0c0b))
* make SonarQube Cloud actually receive coverage ([#61](https://github.com/felixhaegele/fitfinder/issues/61)) ([d9f925b](https://github.com/felixhaegele/fitfinder/commit/d9f925b61e1cc89243362cbd4e61ad922239a403))
* release automation with release-please ([#76](https://github.com/felixhaegele/fitfinder/issues/76)) ([f6a624e](https://github.com/felixhaegele/fitfinder/commit/f6a624e9160cb78ffcf881687f228eb162790d94))
* run the worker's Supabase integration tests in CI ([#95](https://github.com/felixhaegele/fitfinder/issues/95)) ([e3990b1](https://github.com/felixhaegele/fitfinder/commit/e3990b199c84375b3a81cb2d00c813fc6b0d1b22))
* staging and prod Supabase with migrations applied by CI ([#70](https://github.com/felixhaegele/fitfinder/issues/70)) ([1315df7](https://github.com/felixhaegele/fitfinder/commit/1315df72cb79d16d45a1058a25dcd555b395cc30))
