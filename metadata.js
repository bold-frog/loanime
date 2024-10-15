#!/usr/bin/env node

import { HiAnime } from "aniwatch";

console.stdout = console.log;
console.log = console.error;

const hianime = new HiAnime.Scraper();

hianime
  .getEpisodeSources(process.argv[2] + "?ep=" + process.argv[3], "hd-1", process.argv[4])
  .then((data) => console.stdout(JSON.stringify(data)))
  .catch((err) => console.error(err));
