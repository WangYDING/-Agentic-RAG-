# P1-V2-009 recall diagnosis

Date: 2026-11-09

The active snapshot contains GB 50157-2013 clause 4.1.18 on PDF page 38 as
a complete chunk.  It states the line/track conditions, 60 km/h speed,
7.5 m and 1.5 m measurement position, and the 80 dB(A) limit.

In the frozen independent-v2 reproduction, neither the initial Top10 nor the
Grader-triggered retrieval contained 4.1.18.  The initial question produced no
focused queries.  The retry split “specific limit” from “test conditions”, but
used wording that ranked general environmental-noise clauses ahead of the
vehicle measurement clause.  The loss therefore occurred before candidate
fusion, not in final evidence selection.

The repair adds a syntax-based split for questions that jointly ask a measured
quantity's test conditions and limit.  For the established technical concept
“车辆外部运行噪声”, its focused queries use measurement vocabulary already
present in the provision (continuous equivalent noise, running speed and
measurement position).  No article number, numeric answer, extra document, or
larger candidate pool is injected.
