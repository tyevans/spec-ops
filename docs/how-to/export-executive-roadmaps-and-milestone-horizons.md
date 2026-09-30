# How-To: Export Executive Roadmaps and Milestone Horizons

This guide explains how to generate presentation-grade SVG vector visuals and interactive HTML delivery horizon decks from live PRD milestones and tasks using `spec-ops export roadmap`.

---

## 1. Export SVG Roadmap Visual

To export a standalone vector SVG diagram showing milestone horizons, delivery phases, and target completion windows:

```bash
spec-ops export roadmap --format svg --out dist/roadmap.svg
```

The exported SVG diagram uses crisp vector rendering suitable for embedding in presentation slides, executive briefings, or GitHub repository READMEs.

---

## 2. Export Interactive HTML Deck

To generate a zero-dependency HTML presentation deck featuring interactive milestone cards, progress bars, and outcome breakdowns:

```bash
spec-ops export roadmap --format html --out dist/roadmap.html
```

The resulting HTML file runs completely offline with zero external network or CDN dependencies.

---

## 3. Customize Audience and Granularity

To tailor the generated roadmap for leadership presentations or detailed technical reviews, specify the `--audience` and `--granularity` flags:

```bash
spec-ops export roadmap --format html --audience "Executive Leadership" --granularity "Milestones & Outcomes"
```

For technical architecture reviews:

```bash
spec-ops export roadmap --format svg --audience "Engineering" --granularity "Vertical Slices"
```
