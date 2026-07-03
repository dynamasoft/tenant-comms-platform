# Sample Tenant Scenarios (Demo)

Use these with the sample lease (`fixtures/sample_lease.txt`) to demo the platform. Each is a
question a landlord might ask. They map to the workflow's lease retrieval + Florida law +
risk + timeline + message-drafting nodes.

1. **Moved out owing utilities** — "Tenant moved out without notice and still owes utilities.
   What should I do?"
2. **Break lease early** — "My tenant wants to break the lease early. What are my options and
   what should I tell them?"
3. **Did not pay rent** — "The tenant did not pay rent this month. What notice do I serve and
   when does it expire?"
4. **Refuses maintenance access** — "The tenant refuses to let my contractor in for a repair.
   Can I require access?"
5. **Unpaid utilities as rent** — "Does the unpaid utility charge count as additional rent for
   a 3-day notice?"
6. **Lock change after 3-day notice** — "I served a 3-day notice. Can I change the locks yet?"

## Notes for the demo

- Scenarios 3 and 6 exercise the `timeline_calculator` tool (deadline math).
- Scenario 5 exercises the "utilities as additional rent" nuance (lease-dependent).
- Every response must: cite lease passages, separate lease vs Florida law, state uncertainty,
  avoid claiming to be a lawyer, and end with the disclaimer.
