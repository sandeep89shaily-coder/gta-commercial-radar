# Industrial lifecycle investigation baseline

The project lifecycle tracker accepts the private 100-project investigation archive. It preserves the original LC-001–LC-050 IDs and adds LC-051–LC-100. The archive contains the workbook, the 100 reports, the research methodology and machine-readable evidence. Install the archive on the Radar machine with Python 3.11 or later.

```powershell
py -3 gta_project_lifecycle_50.py --results "C:\Radar\results" --import-baseline "C:\Downloads\GTA_Radar_Lifecycle_Baseline_20261126.zip"
```

Use your actual Radar results directory. The command verifies the archive, retains a dated copy under `data/lifecycle/snapshots/`, activates `data/lifecycle/baseline.zip` and writes the lifecycle CSV and status JSON without paid requests. Reimporting an identical archive reuses its snapshot. Database and report files in the archive belong in this git-ignored data folder.

The lifecycle CSV shows the investigation date, historical lifecycle and documented equipment alongside today's review state. A new review still needs fresh, project-specific evidence. Funding dates, general business contacts and engineering predictions do not establish a public bid, purchasing authority or a sale-ready opportunity.

For an expressly approved paid refresh, invoke the same script with `--paid` and the usual configured DeepSeek access. This opts the imported cohort into the existing shared budget and allows the selected projects' historical lifecycle excerpts to be compared with newly retrieved evidence. The full baseline archive, contacts and rankings stay local. The scheduled daily pipeline reads the baseline and includes the lifecycle report without paid lifecycle requests. Other Radar stages follow their existing settings. Do not publish archive or results to the marketing site.
