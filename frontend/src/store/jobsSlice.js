import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

// ── Constants ──────────────────────────────────────────────────────────────────

export const JOB_SOURCES = {
  REMOTEOK: "remoteok",
  HN:       "hn",
  ADZUNA:   "adzuna",
};

export const SORT_OPTIONS = {
  FIT_SCORE_DESC: "fit_score_desc",
  FIT_SCORE_ASC:  "fit_score_asc",
  DATE_DESC:      "date_desc",
  COMPANY_ASC:    "company_asc",
  TITLE_ASC:      "title_asc",
};

export const SCORE_FILTERS = {
  ALL:       { label: "All",       min: 0,   max: 10  },
  STRONG:    { label: "Strong",    min: 7.5, max: 10  },
  GOOD:      { label: "Good",      min: 6.0, max: 7.49 },
  FAIR:      { label: "Fair",      min: 4.0, max: 5.99 },
  WEAK:      { label: "Weak",      min: 0,   max: 3.99 },
};

// ── Initial State ──────────────────────────────────────────────────────────────

const INITIAL_FILTERS = {
  search:       "",
  source:       "all",
  scoreFilter:  "ALL",
  minScore:     0,
  maxScore:     10,
  tags:         [],            // selected tag filters
  hasScore:     false,         // only show scored jobs
  hasCoverLetter: false,       // only show jobs with cover letters
  remote:       false,         // only remote jobs
};

const INITIAL_STATE = {
  // ── Raw data ───────────────────────────────────────────────────────────────
  jobs:           [],          // list[Job] from cache
  jobsWithScores: [],          // list[JobWithScore] from pipeline results
  selectedJobId:  null,

  // ── Filters & Sort ─────────────────────────────────────────────────────────
  filters:        { ...INITIAL_FILTERS },
  sortBy:         SORT_OPTIONS.FIT_SCORE_DESC,

  // ── Pagination ─────────────────────────────────────────────────────────────
  page:           1,
  pageSize:       20,

  // ── Loading states ─────────────────────────────────────────────────────────
  loading:        false,
  scraping:       false,
  error:          null,

  // ── Scrape metadata ────────────────────────────────────────────────────────
  lastScrapedAt:  null,
  scrapeStats:    null,        // { total, sources: { remoteok, hn, adzuna } }
  fromCache:      false,

  // ── Cache stats ────────────────────────────────────────────────────────────
  cacheStats:     null,

  // ── Computed (derived, updated on mutation) ────────────────────────────────
  filteredCount:  0,
  totalCount:     0,
};

// ── Store ──────────────────────────────────────────────────────────────────────

export const useJobsStore = create(
  devtools(
    subscribeWithSelector(
      immer((set, get) => ({
        ...INITIAL_STATE,

        // ── Setters: Raw Jobs ────────────────────────────────────────────────

        setJobs: (jobs) => set((state) => {
          state.jobs      = jobs;
          state.totalCount = jobs.length;
        }, false, "setJobs"),

        setJobsWithScores: (jobsWithScores) => set((state) => {
          state.jobsWithScores = jobsWithScores;
        }, false, "setJobsWithScores"),

        upsertJobWithScore: (jobWithScore) => set((state) => {
          const idx = state.jobsWithScores.findIndex(
            (j) => j.job.id === jobWithScore.job.id
          );
          if (idx >= 0) {
            state.jobsWithScores[idx] = jobWithScore;
          } else {
            state.jobsWithScores.push(jobWithScore);
          }
        }, false, "upsertJobWithScore"),

        setCoverLetter: (jobId, coverLetter) => set((state) => {
          const item = state.jobsWithScores.find((j) => j.job.id === jobId);
          if (item) {
            item.cover_letter = coverLetter;
          }
        }, false, "setCoverLetter"),

        // ── Selection ────────────────────────────────────────────────────────

        selectJob: (jobId) => set((state) => {
          state.selectedJobId = jobId;
        }, false, "selectJob"),

        clearSelection: () => set((state) => {
          state.selectedJobId = null;
        }, false, "clearSelection"),

        // ── Filters ──────────────────────────────────────────────────────────

        setFilter: (key, value) => set((state) => {
          state.filters[key] = value;
          state.page = 1;         // reset pagination on filter change
        }, false, `setFilter/${key}`),

        setSearchQuery: (query) => set((state) => {
          state.filters.search = query;
          state.page = 1;
        }, false, "setSearchQuery"),

        setSourceFilter: (source) => set((state) => {
          state.filters.source = source;
          state.page = 1;
        }, false, "setSourceFilter"),

        setScoreFilter: (filterKey) => set((state) => {
          const band = SCORE_FILTERS[filterKey];
          if (band) {
            state.filters.scoreFilter = filterKey;
            state.filters.minScore    = band.min;
            state.filters.maxScore    = band.max;
          }
          state.page = 1;
        }, false, "setScoreFilter"),

        toggleTag: (tag) => set((state) => {
          const idx = state.filters.tags.indexOf(tag);
          if (idx >= 0) {
            state.filters.tags.splice(idx, 1);
          } else {
            state.filters.tags.push(tag);
          }
          state.page = 1;
        }, false, "toggleTag"),

        toggleRemoteFilter: () => set((state) => {
          state.filters.remote = !state.filters.remote;
          state.page = 1;
        }, false, "toggleRemoteFilter"),

        toggleHasScore: () => set((state) => {
          state.filters.hasScore = !state.filters.hasScore;
          state.page = 1;
        }, false, "toggleHasScore"),

        toggleHasCoverLetter: () => set((state) => {
          state.filters.hasCoverLetter = !state.filters.hasCoverLetter;
          state.page = 1;
        }, false, "toggleHasCoverLetter"),

        resetFilters: () => set((state) => {
          state.filters = { ...INITIAL_FILTERS };
          state.page    = 1;
        }, false, "resetFilters"),

        // ── Sort ─────────────────────────────────────────────────────────────

        setSortBy: (sortBy) => set((state) => {
          state.sortBy = sortBy;
          state.page   = 1;
        }, false, "setSortBy"),

        // ── Pagination ────────────────────────────────────────────────────────

        setPage: (page) => set((state) => {
          state.page = Math.max(1, page);
        }, false, "setPage"),

        nextPage: () => set((state) => {
          const maxPage = Math.ceil(state.filteredCount / state.pageSize);
          state.page = Math.min(state.page + 1, maxPage);
        }, false, "nextPage"),

        prevPage: () => set((state) => {
          state.page = Math.max(1, state.page - 1);
        }, false, "prevPage"),

        setPageSize: (size) => set((state) => {
          state.pageSize = size;
          state.page     = 1;
        }, false, "setPageSize"),

        // ── Loading ───────────────────────────────────────────────────────────

        setLoading: (loading) => set((state) => {
          state.loading = loading;
          if (loading) state.error = null;
        }, false, "setLoading"),

        setScraping: (scraping) => set((state) => {
          state.scraping = scraping;
          if (scraping) state.error = null;
        }, false, "setScraping"),

        setError: (error) => set((state) => {
          state.error   = error;
          state.loading = false;
          state.scraping = false;
        }, false, "setError"),

        clearError: () => set((state) => {
          state.error = null;
        }, false, "clearError"),

        // ── Scrape metadata ───────────────────────────────────────────────────

        setScrapeResult: (result) => set((state) => {
          state.scrapeStats   = result.sources;
          state.lastScrapedAt = new Date().toISOString();
          state.fromCache     = result.from_cache;
          state.totalCount    = result.total;
        }, false, "setScrapeResult"),

        setCacheStats: (stats) => set((state) => {
          state.cacheStats = stats;
        }, false, "setCacheStats"),

        // ── Reset ─────────────────────────────────────────────────────────────

        reset: () => set(() => ({ ...INITIAL_STATE }), false, "reset"),

        // ── Computed Selectors ────────────────────────────────────────────────

        getFilteredJobs: () => {
          const state = get();
          const { filters, sortBy, jobsWithScores, jobs } = state;

          // Use jobsWithScores if available (post-pipeline), else raw jobs
          let items = jobsWithScores.length > 0
            ? jobsWithScores
            : jobs.map((job) => ({ job, match: null, cover_letter: null }));

          // ── Filter: search ────────────────────────────────────────────────
          if (filters.search.trim()) {
            const q = filters.search.toLowerCase();
            items = items.filter(({ job }) =>
              job.title.toLowerCase().includes(q)       ||
              job.company.toLowerCase().includes(q)     ||
              job.description.toLowerCase().includes(q) ||
              job.tags.some((t) => t.toLowerCase().includes(q))
            );
          }

          // ── Filter: source ────────────────────────────────────────────────
          if (filters.source !== "all") {
            items = items.filter(({ job }) => job.source === filters.source);
          }

          // ── Filter: score range ───────────────────────────────────────────
          if (filters.hasScore) {
            items = items.filter(({ match }) => match !== null);
          }
          if (filters.minScore > 0 || filters.maxScore < 10) {
            items = items.filter(({ match }) => {
              if (!match) return filters.minScore === 0;
              return match.fit_score >= filters.minScore &&
                     match.fit_score <= filters.maxScore;
            });
          }

          // ── Filter: cover letter ──────────────────────────────────────────
          if (filters.hasCoverLetter) {
            items = items.filter(({ cover_letter }) => cover_letter !== null);
          }

          // ── Filter: remote ────────────────────────────────────────────────
          if (filters.remote) {
            items = items.filter(({ job }) =>
              job.location.toLowerCase().includes("remote") ||
              job.tags.some((t) => t.toLowerCase() === "remote")
            );
          }

          // ── Filter: tags ──────────────────────────────────────────────────
          if (filters.tags.length > 0) {
            items = items.filter(({ job }) =>
              filters.tags.every((tag) =>
                job.tags.some((t) => t.toLowerCase() === tag.toLowerCase())
              )
            );
          }

          // ── Sort ──────────────────────────────────────────────────────────
          items = [...items].sort((a, b) => {
            switch (sortBy) {
              case SORT_OPTIONS.FIT_SCORE_DESC:
                return (b.match?.fit_score ?? -1) - (a.match?.fit_score ?? -1);
              case SORT_OPTIONS.FIT_SCORE_ASC:
                return (a.match?.fit_score ?? -1) - (b.match?.fit_score ?? -1);
              case SORT_OPTIONS.DATE_DESC:
                return new Date(b.job.scraped_at) - new Date(a.job.scraped_at);
              case SORT_OPTIONS.COMPANY_ASC:
                return a.job.company.localeCompare(b.job.company);
              case SORT_OPTIONS.TITLE_ASC:
                return a.job.title.localeCompare(b.job.title);
              default:
                return 0;
            }
          });

          return items;
        },

        getPaginatedJobs: () => {
          const state    = get();
          const filtered = state.getFilteredJobs();
          const start    = (state.page - 1) * state.pageSize;
          const end      = start + state.pageSize;
          return {
            items:       filtered.slice(start, end),
            total:       filtered.length,
            page:        state.page,
            pageSize:    state.pageSize,
            totalPages:  Math.ceil(filtered.length / state.pageSize),
            hasNext:     end < filtered.length,
            hasPrev:     state.page > 1,
          };
        },

        getJobById: (jobId) => {
          const state = get();
          const found = state.jobsWithScores.find((j) => j.job.id === jobId);
          if (found) return found;
          const rawJob = state.jobs.find((j) => j.id === jobId);
          return rawJob ? { job: rawJob, match: null, cover_letter: null } : null;
        },

        getTopJobs: (n = 5) => {
          const state = get();
          return state.jobsWithScores
            .filter((j) => j.match !== null)
            .sort((a, b) => b.match.fit_score - a.match.fit_score)
            .slice(0, n);
        },

        getScoreDistribution: () => {
          const state = get();
          const dist  = { excellent: 0, good: 0, fair: 0, weak: 0, unscored: 0 };
          const items = state.jobsWithScores.length > 0
            ? state.jobsWithScores
            : state.jobs.map((job) => ({ job, match: null }));

          for (const { match } of items) {
            if (!match) { dist.unscored++;  continue; }
            const s = match.fit_score;
            if      (s >= 8.0) dist.excellent++;
            else if (s >= 6.0) dist.good++;
            else if (s >= 4.0) dist.fair++;
            else               dist.weak++;
          }
          return dist;
        },

        getAvailableTags: () => {
          const state = get();
          const tagCounts = new Map();
          const items = state.jobsWithScores.length > 0
            ? state.jobsWithScores.map((j) => j.job)
            : state.jobs;

          for (const job of items) {
            for (const tag of job.tags || []) {
              const key = tag.toLowerCase();
              tagCounts.set(key, (tagCounts.get(key) || 0) + 1);
            }
          }

          return Array.from(tagCounts.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 30)
            .map(([tag, count]) => ({ tag, count }));
        },

        getSourceCounts: () => {
          const state = get();
          const counts = { remoteok: 0, hn: 0, adzuna: 0 };
          const jobs = state.jobsWithScores.length > 0
            ? state.jobsWithScores.map((j) => j.job)
            : state.jobs;

          for (const job of jobs) {
            if (counts[job.source] !== undefined) {
              counts[job.source]++;
            }
          }
          return counts;
        },

        hasActiveFilters: () => {
          const { filters } = get();
          return (
            filters.search         !== ""    ||
            filters.source         !== "all" ||
            filters.scoreFilter    !== "ALL" ||
            filters.tags.length    >   0     ||
            filters.hasScore                 ||
            filters.hasCoverLetter           ||
            filters.remote
          );
        },
      }))
    ),
    { name: "JobsStore" }
  )
);

// ── Subscriptions ──────────────────────────────────────────────────────────────

// Keep filteredCount in sync whenever jobs/filters/sort change
useJobsStore.subscribe(
  (state) => [
    state.jobs,
    state.jobsWithScores,
    state.filters,
    state.sortBy,
  ],
  () => {
    const filtered = useJobsStore.getState().getFilteredJobs();
    useJobsStore.setState(
      (state) => { state.filteredCount = filtered.length; },
      false,
      "syncFilteredCount"
    );
  },
  { equalityFn: (a, b) => JSON.stringify(a) === JSON.stringify(b) }
);

// ── Convenience Hooks ─────────────────────────────────────────────────────────

export const useJobs           = ()  => useJobsStore((s) => s.jobs);
export const useJobsWithScores = ()  => useJobsStore((s) => s.jobsWithScores);
export const useSelectedJob    = ()  => useJobsStore((s) => s.getJobById(s.selectedJobId));
export const useJobsLoading    = ()  => useJobsStore((s) => s.loading || s.scraping);
export const useJobsError      = ()  => useJobsStore((s) => s.error);
export const useJobFilters     = ()  => useJobsStore((s) => s.filters);
export const usePaginatedJobs  = ()  => useJobsStore((s) => s.getPaginatedJobs());
export const useTopJobs        = (n) => useJobsStore((s) => s.getTopJobs(n));
export const useScoreDist      = ()  => useJobsStore((s) => s.getScoreDistribution());
export const useAvailableTags  = ()  => useJobsStore((s) => s.getAvailableTags());
export const useSourceCounts   = ()  => useJobsStore((s) => s.getSourceCounts());
export const useHasActiveFilters = () => useJobsStore((s) => s.hasActiveFilters());