Shift scheduling
================

The shift scheduler turns tactical actions into deterministic crew-day and machine-day assignments.
It is a FHOPS-style prototype, not a replacement for the FHOPS engine.

Each work item records method, contractor, year, productive hours, and travel hours. Crews and
machines declare supported methods and daily shift hours. The scheduler:

- enforces method skills and contractor matching;
- respects daily crew and machine shift capacity;
- includes travel in the first available shift chunk;
- splits long work items across days;
- records productive and travel hours separately;
- reports named resource and unscheduled violations;
- reports crew and machine utilization.

The model does not include shift calendars, weather, road closures, equipment breakdowns, or labour
rules. Those remain operational constraints for the owner and contractor. FHOPS remains the optional
engine boundary; this scheduler is deterministic evidence for the prototype.
