"""Local rules: role families, seniority, skills. Pure data, compiled into SQL by pipeline.py."""

# (role, regex over lower(title)); first match wins, order matters.
ROLES = [
    ("eng_mgmt", r"\b(engineering|software|software development|platform|infrastructure|data engineering|ml|machine learning|ai|technology) (manager|director)\b"
                 r"|\b(head|director|vp|vice president|svp) of (engineering|software|platform|infrastructure|data engineering|ai|machine learning|technology|product engineering|(global )?it)\b"
                 r"|\bcto\b|chief technology|chief technical|engineering lead\b|\bit (manager|director)\b"),
    ("ml_ai", r"machine learning|\bml\b|\bai (engineer|developer|architect|researcher|scientist|specialist|lead|platform)|\bai/ml\b|deep learning|computer vision|"
              r"\bnlp\b|\bllms?\b|genai|generative ai|applied scien|research scientist|mlops|perception engineer|"
              r"(engineer|developer|scientist|researcher)\b.*\b(ai|ml)\b"),
    ("data_eng", r"data (engineer|platform|infrastructure|architect|ops)|data \w+ engineer|analytics engineer|\betl\b|big data|dataops|data warehouse"),
    ("data_analytics", r"data scien|data analyst|business intelligence|\bbi (developer|engineer|analyst)|quantitative (analyst|researcher|developer)|"
                       r"\bquant\b|statistician|product analyst|decision scien|analytics (lead|manager)"),
    ("security", r"security (engineer|architect|analyst|researcher|specialist|consultant|operations)|appsec|devsecops|penetration|pentest|"
                 r"\bsoc\b|cyber|infosec|information security|red team|blue team|detection engineer|threat (intel|hunt|detect)|vulnerability|iam engineer"),
    ("devops", r"devops|\bsre\b|site reliability|reliability engineer|platform engineer|infrastructure engineer|cloud (engineer|architect|ops|developer)|"
               r"kubernetes|build engineer|release engineer|systems? engineer.*(linux|cloud|infrastructure)|production engineer|observability"),
    ("mobile", r"\bios\b|android|react native|flutter|mobile (software|app|application)?\s*(engineer|developer|architect|lead)|(engineer|developer)\b.*\bmobile"),
    ("fullstack", r"full[- ]?stack"),
    ("frontend", r"front[- ]?end|\bui (engineer|developer)|web developer|javascript|typescript|react|angular|vue|web engineer"),
    ("backend", r"back[- ]?end|\bapi (engineer|developer)|server(-side)? (engineer|developer)|"
                r"\b(java|python|golang|go|ruby|rails|php|node(\.js)?|\.net|c#|scala|elixir|rust|c\+\+|kotlin|clojure|haskell|erlang|django|laravel) (developer|engineer|programmer)"),
    ("embedded", r"embedded (software|systems?|engineer|developer|c|linux|firmware)|firmware|fpga|\basic\b|\brtl\b|silicon|(design )?verification engineer|"
                 r"hardware (engineer|developer)|robotics (engineer|software)|\bdsp\b|autonomy engineer|controls? software|kernel|driver (engineer|developer)|compiler"),
    ("qa", r"\bqa\b|quality assurance (engineer|analyst|automation)|(software|automation|qa) test(ing)? (engineer|developer|analyst)|"
           r"test automation|\bsdet\b|software tester|automation tester|manual tester|\bqe\b"),
    ("gamedev", r"game (developer|programmer|engineer|designer)|gameplay|\bunity\b|\bunreal\b|graphics (engineer|programmer)|rendering engineer|technical artist"),
    ("blockchain", r"blockchain|smart contract|solidity|web3|crypto(currency)? engineer|protocol engineer|defi"),
    ("devrel", r"developer (advocate|relations|evangelist|experience)|devrel|developer community"),
    ("solutions", r"solutions? (engineer|architect|consultant)|sales engineer|pre-?sales engineer|forward[- ]deployed|customer engineer|"
                  r"implementation engineer|technical account manager|technical consultant"),
    ("architect", r"(software|enterprise|technical|application|systems|integration) architect"),
    ("tech_writing", r"technical writer|documentation engineer|api writer"),
    ("support_eng", r"(technical|application|production|software|it) support (engineer|specialist|analyst)|support engineer"),
    ("product", r"product (manager|owner|lead|director)|technical program manager|\btpm\b|program manager.*(technical|engineering|software)|"
                r"technical project manager|scrum master|agile coach|head of product|vp(,| of) product|chief product"),
    ("design", r"product designer|\bux\b|\bui\b|ui/ux|ux/ui|interaction designer|user research|design systems"),
    ("it_ops", r"\bit (support|administrator|engineer|specialist|analyst|technician)|system(s)? administrator|sysadmin|network engineer|"
               r"helpdesk|help desk|desktop support|database administrator|\bdba\b|servicenow|salesforce (developer|engineer|admin)|sap (developer|consultant|abap)"),
    ("software", r"software|(web|application|app|backend|frontend|mobile|java|python|\.net|php|ruby|c#|c\+\+|golang|game|full ?stack|front ?end|back ?end|sql|database|bi|salesforce|cloud|rpa|automation) (developer|programmer)|"
                 r"^developer\b|\bdeveloper$|\bswe\b|\bsde\b|member of technical staff|\bmts\b|tech(nical)? lead|engineering (intern|fellow)|"
                 r"product engineer|founding engineer|research engineer|computer scien|"
                 r"software-?entwickler|anwendungsentwickler|webentwickler|(fullstack|backend|frontend|java|python|\.net|web)-?entwickler|"
                 r"développeur|desarrollador|ontwikkelaar|programador"),
]
# Titles that match the patterns above but are not tech roles.
NOT_TECH = (r"business develop|property|real estate|sales (manager|director|representative|executive|development)|account executive|"
            r"recruit|talent acquisition|marketing manager|nurse|\bdriver\b|warehouse|cashier|mechanic|electrician|plumber|\bchef\b|teacher|"
            r"executive assistant|assistant to|contributor|participant|physician|task-based|annotat|ai trainer|\btutor|phlebotom|"
            r"\bcnc\b|press brake|machine programmer|clinical data|development (director|officer|associate)|fundrais|store manager")

# (level, regex over lower(title)); first match wins.
SENIORITY = [
    ("intern", r"\bintern(ship)?\b|praktikum|praktikant|werkstudent|working student|\bco-?op\b|apprentice|trainee|stagiaire|\bstage\b|alternance"),
    ("director", r"\bdirector\b|\bhead of\b|\bvp\b|vice president|\bchief\b|\bcto\b|\bsvp\b|\bevp\b"),
    ("manager", r"\bmanager\b|\bmgr\b"),
    ("principal", r"principal|distinguished|\bfellow\b|\barchitect\b"),
    ("staff", r"\bstaff\b"),
    ("lead", r"\blead\b|\bleader\b|team lead|tech lead"),
    ("senior", r"\bsenior\b|\bsr\.?\b|\biii\b|\biv\b|\blevel (3|4)\b|\bl[45]\b|expert"),
    ("junior", r"\bjunior\b|\bjr\.?\b|entry[- ]level|graduate|new grad|\bgrad\b|early career|\bassociate\b|\bi\b$|\blevel 1\b"),
]

# Skills: canonical -> (category, aliases). Aliases are matched as whole lowercase tokens after
# PHRASES rewriting. Ambiguous names (Go, R, C, Swift, ...) live in CONTEXT_SKILLS instead.
SKILLS = {
    # languages
    "Python": ("language", "python python3"), "JavaScript": ("language", "javascript js ecmascript es6"),
    "TypeScript": ("language", "typescript"), "Java": ("language", "java jvm j2ee"),
    "Kotlin": ("language", "kotlin"), "Scala": ("language", "scala"), "C++": ("language", "c++ cpp"),
    "C#": ("language", "c# csharp"), "Rust": ("language", "rust rustlang"), "Golang": ("language", "golang"),
    "Ruby": ("language", "ruby"), "PHP": ("language", "php"), "Elixir": ("language", "elixir"),
    "Erlang": ("language", "erlang"), "Haskell": ("language", "haskell"), "Clojure": ("language", "clojure"),
    "OCaml": ("language", "ocaml"), "F#": ("language", "f#"), "Zig": ("language", "zig"),
    "Objective-C": ("language", "objective-c objc"), "Perl": ("language", "perl"), "Lua": ("language", "lua"),
    "Bash": ("language", "bash zsh"), "PowerShell": ("language", "powershell"), "SQL": ("language", "sql"),
    "MATLAB": ("language", "matlab"), "Solidity": ("language", "solidity"), "Fortran": ("language", "fortran"),
    "COBOL": ("language", "cobol"), "VHDL": ("language", "vhdl"), "Verilog": ("language", "verilog systemverilog"),
    "Groovy": ("language", "groovy"), "Apex": ("language", "apex"), "ABAP": ("language", "abap"),
    "WebAssembly": ("language", "webassembly wasm"), "GraphQL": ("api", "graphql"),
    # frontend
    "React": ("frontend", "reactjs react.js"), "Next.js": ("frontend", "next.js nextjs"),
    "Vue": ("frontend", "vue vuejs vue.js nuxt nuxtjs"), "Angular": ("frontend", "angular angularjs"),
    "Svelte": ("frontend", "svelte sveltekit"), "Redux": ("frontend", "redux"), "Tailwind": ("frontend", "tailwind tailwindcss"),
    "HTML/CSS": ("frontend", "html html5 css css3 sass scss"), "jQuery": ("frontend", "jquery"),
    "Webpack": ("frontend", "webpack vite esbuild"), "Three.js": ("frontend", "three.js threejs webgl"),
    "Storybook": ("frontend", "storybook"), "Remix": ("frontend", "remix"),
    # mobile
    "React Native": ("mobile", "react_native"), "Flutter": ("mobile", "flutter"), "SwiftUI": ("mobile", "swiftui"),
    "iOS": ("mobile", "ios xcode uikit"), "Android": ("mobile", "android jetpack"), "Dart": ("mobile", "dart"),
    # backend / frameworks
    "Node.js": ("backend", "node.js nodejs"), "Express": ("backend", "express.js expressjs"),
    "NestJS": ("backend", "nestjs nest.js"), "Django": ("backend", "django"), "Flask": ("backend", "flask"),
    "FastAPI": ("backend", "fastapi"), "Rails": ("backend", "rails ror ruby_on_rails"), "Laravel": ("backend", "laravel symfony"),
    "Spring": ("backend", "spring_boot springboot spring_framework"), ".NET": ("backend", "dotnet asp.net aspnet .net_core"),
    "gRPC": ("api", "grpc protobuf protocol_buffers"), "REST": ("api", "restful rest_api"),
    "Microservices": ("backend", "microservices microservice"), "Kafka": ("backend", "kafka"),
    "RabbitMQ": ("backend", "rabbitmq amqp"), "Celery": ("backend", "celery"),
    "WebSockets": ("backend", "websocket websockets"), "Deno": ("backend", "deno"), "Bun": ("backend", "bun"),
    # databases
    "PostgreSQL": ("database", "postgres postgresql psql"), "MySQL": ("database", "mysql mariadb"),
    "MongoDB": ("database", "mongodb mongo"), "Redis": ("database", "redis"), "Elasticsearch": ("database", "elasticsearch opensearch"),
    "Cassandra": ("database", "cassandra scylladb"), "DynamoDB": ("database", "dynamodb"), "SQLite": ("database", "sqlite"),
    "Oracle DB": ("database", "oracle_db plsql pl/sql"), "SQL Server": ("database", "mssql sql_server t-sql tsql"),
    "ClickHouse": ("database", "clickhouse"), "Neo4j": ("database", "neo4j"), "Supabase": ("database", "supabase"),
    "Firebase": ("database", "firebase firestore"), "CockroachDB": ("database", "cockroachdb"),
    "Vector DB": ("database", "pinecone weaviate qdrant milvus pgvector chromadb"),
    # data
    "Spark": ("data", "spark pyspark"), "Airflow": ("data", "airflow"), "dbt": ("data", "dbt"),
    "Snowflake": ("data", "snowflake"), "BigQuery": ("data", "bigquery"), "Redshift": ("data", "redshift"),
    "Databricks": ("data", "databricks delta_lake"), "Hadoop": ("data", "hadoop hive hdfs"), "Flink": ("data", "flink"),
    "Pandas": ("data", "pandas numpy polars"), "Tableau": ("data", "tableau"), "Power BI": ("data", "power_bi powerbi"),
    "Looker": ("data", "looker"), "Dagster": ("data", "dagster"), "Kinesis": ("data", "kinesis"),
    "Trino": ("data", "trino presto athena"), "DuckDB": ("data", "duckdb"), "Iceberg": ("data", "apache_iceberg"),
    # ml / ai
    "PyTorch": ("ml", "pytorch"), "TensorFlow": ("ml", "tensorflow keras"),
    "scikit-learn": ("ml", "scikit-learn sklearn"), "LLMs": ("ml", "llm llms gpt large_language_models"),
    "LangChain": ("ml", "langchain llamaindex langgraph"), "Hugging Face": ("ml", "huggingface hugging_face"),
    "RAG": ("ml", "rag retrieval-augmented"), "Computer Vision": ("ml", "computer_vision opencv"),
    "NLP": ("ml", "nlp natural_language_processing"), "MLOps": ("ml", "mlops mlflow kubeflow"),
    "CUDA": ("ml", "cuda triton"), "XGBoost": ("ml", "xgboost lightgbm catboost"), "Reinforcement Learning": ("ml", "reinforcement_learning rlhf"),
    "Fine-tuning": ("ml", "fine-tuning finetuning lora"), "Agents": ("ml", "ai_agents agentic"),
    # cloud / devops
    "AWS": ("cloud", "aws amazon_web_services ec2 eks"), "GCP": ("cloud", "gcp google_cloud gke"),
    "Azure": ("cloud", "azure"), "Kubernetes": ("devops", "kubernetes k8s helm"), "Docker": ("devops", "docker containers"),
    "Terraform": ("devops", "terraform opentofu pulumi"), "Ansible": ("devops", "ansible"),
    "CI/CD": ("devops", "ci/cd cicd jenkins github_actions gitlab_ci circleci argocd"),
    "Linux": ("devops", "linux unix ubuntu debian rhel"), "Prometheus": ("devops", "prometheus grafana"),
    "Datadog": ("devops", "datadog"), "Nginx": ("devops", "nginx"), "Istio": ("devops", "istio"),
    "Serverless": ("cloud", "serverless"), "Cloudflare": ("cloud", "cloudflare"), "Vercel": ("cloud", "vercel"),
    "OpenTelemetry": ("devops", "opentelemetry otel"), "Git": ("devops", "git github gitlab bitbucket"),
    # testing / security / other
    "Jest": ("testing", "jest vitest"), "Cypress": ("testing", "cypress playwright selenium"),
    "Pytest": ("testing", "pytest"), "TDD": ("testing", "tdd"), "OAuth": ("security", "oauth oidc saml sso"),
    "SIEM": ("security", "siem splunk"), "Blockchain": ("other", "blockchain ethereum evm web3 defi"),
    "Unity": ("other", "unity3d"), "Unreal": ("other", "unreal ue5"), "ROS": ("other", "ros ros2"),
    "Embedded C": ("other", "embedded_c rtos freertos"), "Figma": ("design", "figma"),
    "Salesforce": ("other", "salesforce"), "SAP": ("other", "sap"), "ServiceNow": ("other", "servicenow"),
    "Shopify": ("other", "shopify"), "WordPress": ("other", "wordpress"),
}

# Lowercase phrase rewrites applied before tokenizing (multi-word skills -> one token).
PHRASES = [
    (r"react[ -]native", " react_native "), (r"\.net core", " .net_core "), (r"(^|[^a-z])\.net\b", " dotnet "),
    (r"ruby on rails", " ruby_on_rails "), (r"spring[ -]boot", " spring_boot "), (r"spring framework", " spring_framework "),
    (r"google cloud( platform)?", " google_cloud "), (r"amazon web services", " amazon_web_services "),
    (r"github actions", " github_actions "), (r"gitlab[ -]ci", " gitlab_ci "), (r"power ?bi", " power_bi "),
    (r"machine learning", " machine_learning "), (r"computer vision", " computer_vision "),
    (r"natural language processing", " natural_language_processing "), (r"large language models?", " large_language_models "),
    (r"reinforcement learning", " reinforcement_learning "), (r"hugging ?face", " hugging_face "),
    (r"protocol buffers", " protocol_buffers "), (r"sql server", " sql_server "), (r"oracle (db|database)", " oracle_db "),
    (r"delta lake", " delta_lake "), (r"ci ?/ ?cd", " cicd "), (r"pl/sql", " plsql "), (r"rest(ful)? apis?", " rest_api "), (r"apache iceberg", " apache_iceberg "), (r"embedded c\b", " embedded_c "), (r"\b(?:ai|llm|autonomous|coding|conversational|voice) agents?\b|\bagent loops?\b|\btool[- ]call(?:s|ing)\b|\bfunction[- ]calling\b", " ai_agents "),
]

# Ambiguous names: matched case-sensitively in the original text, only in a tech context.
CONTEXT_SKILLS = {
    "Golang": r"\bGo(,|/| and | or |\)| \(|lang| developer| engineer| programming| services| microservices|-based)",
    "R": r"(^|[\s,(/])R(,|/| and | or |\)| programming| language| Studio|Shiny)",
    "C": r"(^|[\s,(/])C(,|/C\+\+| and | or |\)| programming| language)",
    "Swift": r"\bSwift(,|/| and | or |\)|UI| developer| engineer| programming)",
    "React": r"\bReact(,|/| and | or |\)|\.js|JS| developer| engineer| Native| hooks| components|\b)",
    "Julia": r"\bJulia(,|/| and | or |\)| programming| language)",
    "Spring": r"\bSpring (Boot|Framework|Cloud|MVC|Data|Security)",
    "Express": r"\bExpress(\.js|JS)",
    "Rust": r"\bRust\b",
    "REST": r"\bREST(ful)?\b",  # upper-case REST is the API style; lower-case "rest" is ordinary English
}

# Static FX rates to USD for salary normalisation.
# ponytail: static rates; good to ~10%, swap for a daily FX fetch if exact USD comparisons matter.
FX = {"USD": 1, "EUR": 1.08, "GBP": 1.27, "CAD": 0.72, "AUD": 0.65, "NZD": 0.6, "CHF": 1.12, "INR": 0.012,
      "SEK": 0.094, "NOK": 0.092, "DKK": 0.145, "PLN": 0.25, "CZK": 0.043, "HUF": 0.0027, "RON": 0.22,
      "JPY": 0.0066, "SGD": 0.74, "HKD": 0.128, "CNY": 0.14, "KRW": 0.00073, "TWD": 0.031, "BRL": 0.18,
      "MXN": 0.055, "ARS": 0.001, "CLP": 0.0011, "COP": 0.00025, "ILS": 0.27, "AED": 0.27, "ZAR": 0.055,
      "TRY": 0.03, "PHP": 0.017, "IDR": 0.000062, "MYR": 0.21, "THB": 0.028, "VND": 0.00004, "NGN": 0.00065,
      "KES": 0.0077, "EGP": 0.02, "PKR": 0.0036, "UAH": 0.024, "BGN": 0.55, "ISK": 0.0072, "SAR": 0.27}
PERIOD = {"YEAR": 1, "MONTH": 12, "WEEK": 52, "DAY": 260, "HOUR": 2080}

# Direct sources beat aggregators when the same job appears twice.
AGGREGATORS = {"builtin": 3, "welcometothejungle": 2, "weworkremotely": 2, "wellfound": 1, "ycombinator": 1, "getonbrd": 2}

# Location-text fallback when the source gives no country_iso.
def _places(spec: str) -> dict:
    out = {}
    for line in spec.strip().splitlines():
        iso, names = line.split(":")
        out |= {n.strip(): iso.strip() for n in names.split("|")}
    return out


PLACES = _places("""
US: united states|usa|u.s.|u.s.a.|united states of america|san francisco|sf|new york|new york city|nyc|seattle|austin|cupertino|sunnyvale|mountain view|palo alto|menlo park|san jose|santa clara|redmond|bellevue|los angeles|boston|chicago|denver|atlanta|washington dc|washington, d.c.|san diego|raleigh|dallas|houston|miami|portland|pittsburgh|philadelphia|salt lake city|minneapolis|detroit|phoenix|nashville|charlotte|irvine|bay area|sf bay area|silicon valley
IN: india|ind|bengaluru|bangalore|bangalore urban|hyderabad|pune|mumbai|chennai|gurgaon|gurugram|noida|delhi|new delhi|kolkata|ahmedabad|kochi|coimbatore|trivandrum|jaipur|karnataka|karnātaka|telangana|maharashtra|tamil nadu
GB: united kingdom|uk|gbr|england|scotland|wales|great britain|london|manchester|edinburgh|bristol|birmingham|leeds|glasgow|belfast|oxford
CA: canada|can|toronto|vancouver|montreal|montréal|ottawa|waterloo|calgary|ontario|british columbia|quebec|québec
DE: germany|deutschland|deu|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|stuttgart|düsseldorf|dusseldorf|leipzig
FR: france|fra|paris|lyon|toulouse|marseille|nantes|lille|bordeaux|sophia antipolis
NL: netherlands|the netherlands|nederland|nld|amsterdam|rotterdam|eindhoven|utrecht|the hague|den haag
IE: ireland|irl|dublin|cork|galway
ES: spain|españa|esp|madrid|barcelona|valencia|málaga|malaga|seville
PT: portugal|prt|lisbon|lisboa|porto
PL: poland|polska|pol|warsaw|warszawa|kraków|krakow|wrocław|wroclaw|gdańsk|gdansk|poznań|poznan|łódź
CH: switzerland|che|zurich|zürich|geneva|genève|basel|lausanne|zug
SE: sweden|swe|stockholm|gothenburg|göteborg|malmö
DK: denmark|dnk|copenhagen|københavn|aarhus
NO: norway|nor|oslo
FI: finland|fin|helsinki|espoo
AT: austria|aut|vienna|wien|graz
BE: belgium|bel|brussels|bruxelles|antwerp|ghent
CZ: czechia|czech republic|cze|prague|praha|brno
RO: romania|rou|bucharest|bucurești|cluj-napoca|iasi
HU: hungary|hun|budapest
GR: greece|grc|athens
IL: israel|isr|tel aviv|tel aviv-yafo|haifa|jerusalem|herzliya
AE: united arab emirates|uae|are|dubai|abu dhabi
SA: saudi arabia|riyadh|jeddah
QA: qatar|doha
SG: singapore|sgp
JP: japan|jpn|tokyo|osaka|kyoto
CN: china|chn|shanghai|beijing|shenzhen|hangzhou|guangzhou
HK: hong kong|hong kong sar
TW: taiwan|twn|taipei|hsinchu
KR: south korea|korea|kor|seoul
AU: australia|aus|sydney|melbourne|brisbane|perth
NZ: new zealand|auckland|wellington
BR: brazil|brasil|bra|são paulo|sao paulo|rio de janeiro|belo horizonte
MX: mexico|méxico|mex|mexico city|ciudad de méxico|guadalajara|monterrey
AR: argentina|buenos aires|córdoba
CL: chile|santiago
CO: colombia|bogotá|bogota|medellín|medellin
PE: peru|lima
UY: uruguay|montevideo
CR: costa rica|san josé
PH: philippines|phl|manila|makati|taguig|cebu
VN: vietnam|viet nam|ho chi minh city|hanoi
ID: indonesia|jakarta
MY: malaysia|kuala lumpur|penang
TH: thailand|bangkok
PK: pakistan|karachi|lahore|islamabad
EG: egypt|cairo
NG: nigeria|lagos
KE: kenya|nairobi
ZA: south africa|cape town|johannesburg
TR: turkey|türkiye|istanbul|ankara
UA: ukraine|kyiv|lviv
EE: estonia|tallinn
LT: lithuania|vilnius
LV: latvia|riga
BG: bulgaria|sofia
HR: croatia|zagreb
RS: serbia|belgrade
LU: luxembourg
CY: cyprus|limassol|nicosia
MT: malta
""")
US_STATES = set("al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy dc".split()) | set(
    "california|texas|washington|massachusetts|illinois|colorado|georgia|virginia|north carolina|florida|oregon|utah|arizona|"
    "pennsylvania|new jersey|ohio|michigan|minnesota|maryland|district of columbia".split("|"))
ISO2 = set(PLACES.values())
