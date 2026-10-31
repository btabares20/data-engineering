import re


TAXONOMY_VERSION = "2026-10-31"
ALIASES = {
    "Python": ("python",), "SQL": ("sql", "structured query language"),
    "Java": ("java",), "JavaScript": ("javascript",), "TypeScript": ("typescript",),
    "C++": ("c++",), "C#": ("c#",), ".NET": (".net", "dotnet", "asp.net"),
    "Go": ("golang", "go programming"), "Scala": ("scala",), "Bash": ("bash", "shell scripting"),
    "PostgreSQL": ("postgresql", "postgres"), "MySQL": ("mysql",), "SQL Server": ("sql server", "mssql"),
    "Oracle": ("oracle",), "MongoDB": ("mongodb",), "Redis": ("redis",),
    "Snowflake": ("snowflake",), "BigQuery": ("bigquery", "big query"), "Redshift": ("redshift",),
    "Databricks": ("databricks",), "Apache Spark": ("apache spark", "pyspark", "spark sql"),
    "Apache Kafka": ("apache kafka", "kafka"), "Apache Airflow": ("apache airflow", "airflow"),
    "dbt": ("dbt",), "AWS": ("aws", "amazon web services"), "Azure": ("azure",),
    "Google Cloud": ("gcp", "google cloud"), "Docker": ("docker",), "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",), "Git": ("git",), "CI/CD": ("ci/cd", "continuous integration"),
    "Power BI": ("power bi", "powerbi"), "Tableau": ("tableau",), "Excel": ("excel",),
    "ETL": ("etl",), "ELT": ("elt",), "Data modeling": ("data modeling", "data modelling"),
    "Data warehousing": ("data warehousing", "data warehouse"),
    "Communication": ("communication skills", "written communication", "verbal communication"),
    "Stakeholder management": ("stakeholder management", "stakeholder engagement"),
    "Project management": ("project management",), "Agile": ("agile", "scrum"),
    "Problem solving": ("problem solving", "problem-solving"),
    "Customer service": ("customer service",), "Accounting": ("accounting",),
    "Bookkeeping": ("bookkeeping",), "Payroll": ("payroll",),
    "Microsoft Office": ("microsoft office", "ms office"),
    "First aid": ("first aid",), "CPR": ("cpr",),
    "Driver licence": ("driver licence", "driver's licence", "drivers licence", "driver license", "driver's license"),
    "Forklift operation": ("forklift",), "Welding": ("welding",),
    "Carpentry": ("carpentry",), "Nursing": ("nursing", "registered nurse"),
    "Teaching": ("teaching",), "Teamwork": ("teamwork", "team work"),
    "Time management": ("time management",),

}
PATTERNS = {
    skill: re.compile(r"(?<![\w+#])(?:" + "|".join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)) + r")(?![\w+#])", re.I)
    for skill, aliases in ALIASES.items()
}
PATTERNS["Excel"] = re.compile(r"(?<!\w)(?:microsoft excel|ms excel|(?-i:Excel))(?!\w)", re.I)
REQUIRED = re.compile(r"\b(must|required|essential|mandatory|need to have)\b", re.I)
PREFERRED = re.compile(r"\b(preferred|desirable|nice to have|bonus|advantage|ideally)\b", re.I)
NEGATED = re.compile(r"\b(not required|not essential|no .{0,50}(?:required|necessary)|do not need|don't need)\b", re.I)
REQUIRED_HEADINGS = {"requirements", "required skills", "essential skills", "essential requirements", "must have"}
PREFERRED_HEADINGS = {"preferred skills", "desirable skills", "nice to have"}
NEUTRAL_HEADINGS = {"responsibilities", "about us", "about the role", "benefits", "what we offer"}


def extract_skills(description):
    mentioned, required, evidence = set(), set(), []
    section = "mentioned"
    for line in (description or "").splitlines():
        heading = line.strip().rstrip(":").casefold()
        if heading in REQUIRED_HEADINGS:
            section = "required"
            continue
        if heading in PREFERRED_HEADINGS:
            section = "preferred"
            continue
        if heading in NEUTRAL_HEADINGS:
            section = "mentioned"
            continue
        if line.rstrip().endswith(":"):
            section = "mentioned"
        for clause in re.split(r"(?<=[.!?])\s+|;|\bbut\b", line, flags=re.I):
            explicit_required = bool(REQUIRED.search(clause))
            preferred = bool(PREFERRED.search(clause)) or section == "preferred"
            negated = bool(NEGATED.search(clause))
            classification = "mentioned"
            if not negated and not preferred and (explicit_required or section == "required"):
                classification = "required"
            elif preferred and not negated:
                classification = "preferred"
            for skill, pattern in PATTERNS.items():
                match = pattern.search(clause)
                if match is None:
                    continue
                mentioned.add(skill)
                if classification == "required":
                    required.add(skill)
                evidence.append({"skill": skill, "classification": classification, "text": clause.strip()[:500], "match": match.group()})
    return {
        "skills_mentioned": sorted(mentioned),
        "skills_required": sorted(required),
        "skills_evidence": evidence,
        "skills_taxonomy_version": TAXONOMY_VERSION,
    }
