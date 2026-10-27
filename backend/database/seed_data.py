"""Seed dataset for the Academic Collaboration Network.

The sample records from the Review-1 document (R001-R005, P001-P005, VIT, IIT Madras,
and the example relationships) are kept exactly. All other records are synthetic but
internally consistent:

* every researcher works at exactly one institution and belongs to a department of
  that same institution;
* a paper only cites papers published in the same year or earlier;
* each paper has 1-3 topics and at most one venue (a Conference or a Journal);
* COLLABORATED_WITH is *derived* from co-authorship by `seed.py`, plus the explicit
  pairs from the review (which are also backed by co-authored papers here).

People, e-mail addresses and DOIs are fictional. DOIs use the 10.5555 prefix, which is
reserved for examples. Conference names/years/locations are illustrative.
"""
from __future__ import annotations

# ---------------------------------------------------------------- Institutions
# (institutionId, name, location, type, emailDomain)
INSTITUTIONS = [
    ("I001", "VIT", "Vellore, Tamil Nadu", "Private University", "vit.example.ac.in"),
    ("I002", "IIT Madras", "Chennai, Tamil Nadu", "Public Institute", "iitm.example.ac.in"),
    ("I003", "IIT Bombay", "Mumbai, Maharashtra", "Public Institute", "iitb.example.ac.in"),
    ("I004", "IIT Delhi", "New Delhi, Delhi", "Public Institute", "iitd.example.ac.in"),
    ("I005", "IISc Bangalore", "Bengaluru, Karnataka", "Public Research Institute", "iisc.example.ac.in"),
    ("I006", "IIIT Hyderabad", "Hyderabad, Telangana", "Deemed University", "iiith.example.ac.in"),
    ("I007", "NIT Trichy", "Tiruchirappalli, Tamil Nadu", "Public Institute", "nitt.example.edu"),
    ("I008", "BITS Pilani", "Pilani, Rajasthan", "Private University", "bits.example.ac.in"),
    ("I009", "IIT Kharagpur", "Kharagpur, West Bengal", "Public Institute", "iitkgp.example.ac.in"),
    ("I010", "TCS Research", "Pune, Maharashtra", "Industry Research Lab", "tcs.example.com"),
]

# ---------------------------------------------------------------- Departments
# (departmentId, name, institutionId)
DEPARTMENTS = [
    ("VIT-SCOPE", "School of Computer Science and Engineering", "I001"),
    ("VIT-SITE", "School of Information Technology and Engineering", "I001"),
    ("IITM-CSE", "Department of Computer Science and Engineering", "I002"),
    ("IITM-DSAI", "Department of Data Science and AI", "I002"),
    ("IITB-CSE", "Department of Computer Science and Engineering", "I003"),
    ("IITB-EE", "Department of Electrical Engineering", "I003"),
    ("IITD-CSE", "Department of Computer Science and Engineering", "I004"),
    ("IITD-MATH", "Department of Mathematics", "I004"),
    ("IISC-CDS", "Department of Computational and Data Sciences", "I005"),
    ("IISC-CSA", "Department of Computer Science and Automation", "I005"),
    ("IIITH-CSE", "Department of Computer Science and Engineering", "I006"),
    ("IIITH-SEC", "Centre for Security and Cryptography", "I006"),
    ("NITT-CSE", "Department of Computer Science and Engineering", "I007"),
    ("BITS-CSIS", "Department of Computer Science and Information Systems", "I008"),
    ("IITKGP-CSE", "Department of Computer Science and Engineering", "I009"),
    ("TCS-AILAB", "AI and Data Research Lab", "I010"),
]

# ---------------------------------------------------------------- Topics
# (topicId, name, description)
TOPICS = [
    ("T001", "Artificial Intelligence", "Systems that perceive, reason, plan and act intelligently."),
    ("T002", "Machine Learning", "Algorithms that learn patterns and models from data."),
    ("T003", "Cybersecurity", "Protecting systems, networks and data from attacks."),
    ("T004", "Graph Databases", "Storage and querying of highly connected data as nodes and relationships."),
    ("T005", "Data Science", "Extracting knowledge and insight from structured and unstructured data."),
    ("T006", "Deep Learning", "Multi-layer neural networks for representation learning."),
    ("T007", "Natural Language Processing", "Computational analysis and generation of human language."),
    ("T008", "Computer Vision", "Understanding images and video with algorithms."),
    ("T009", "Network Security", "Securing communication networks and detecting intrusions."),
    ("T010", "Cryptography", "Mathematical techniques for secure communication and verification."),
    ("T011", "Distributed Systems", "Coordinating computation and storage across many machines."),
    ("T012", "Cloud Computing", "On-demand, elastic computing resources delivered over a network."),
    ("T013", "Social Network Analysis", "Studying structure and dynamics of social and academic networks."),
    ("T014", "Information Retrieval", "Searching, ranking and organising large document collections."),
    ("T015", "Healthcare Informatics", "Data-driven methods for clinical and public-health problems."),
]

# ---------------------------------------------------------------- Conferences
# (conferenceId, name, year, location)
CONFERENCES = [
    ("C001", "NeurIPS", 2024, "Vancouver, Canada"),
    ("C002", "ICML", 2025, "Vancouver, Canada"),
    ("C003", "KDD", 2025, "Toronto, Canada"),
    ("C004", "SIGMOD", 2025, "Berlin, Germany"),
    ("C005", "VLDB", 2024, "Guangzhou, China"),
    ("C006", "IEEE S&P", 2025, "San Francisco, USA"),
    ("C007", "ACM CCS", 2024, "Salt Lake City, USA"),
    ("C008", "ACL", 2025, "Vienna, Austria"),
    ("C009", "CODS-COMAD", 2024, "Bengaluru, India"),
    ("C010", "CVPR", 2025, "Nashville, USA"),
]

# ---------------------------------------------------------------- Journals (schema extension)
# (journalId, name, publisher, field)
JOURNALS = [
    ("J001", "IEEE Transactions on Knowledge and Data Engineering", "IEEE", "Data Engineering"),
    ("J002", "ACM Transactions on Database Systems", "ACM", "Databases"),
    ("J003", "Journal of Machine Learning Research", "JMLR", "Machine Learning"),
    ("J004", "IEEE Transactions on Information Forensics and Security", "IEEE", "Security"),
    ("J005", "Computers & Security", "Elsevier", "Security"),
    ("J006", "Journal of Biomedical Informatics", "Elsevier", "Healthcare Informatics"),
]

# ---------------------------------------------------------------- Researchers
# (researcherId, name, specialization, experienceYears, departmentId)
# Institution is derived from the department, so WORKS_AT and BELONGS_TO always agree.
RESEARCHERS = [
    # --- Review-1 sample records (kept exactly) ---
    ("R001", "Alice Sharma", "Machine Learning", 8, "VIT-SCOPE"),
    ("R002", "Rahul Kumar", "Graph Databases", 9, "IITM-CSE"),
    ("R003", "Priya Singh", "Data Science", 6, "IISC-CDS"),
    ("R004", "Arjun Patel", "Cybersecurity", 11, "IITB-CSE"),
    ("R005", "Neha Gupta", "Artificial Intelligence", 10, "IITM-DSAI"),
    # --- AI / ML cluster ---
    ("R006", "Vikram Rao", "Deep Learning", 12, "IITB-CSE"),
    ("R007", "Ananya Iyer", "Natural Language Processing", 7, "IIITH-CSE"),
    ("R008", "Karthik Menon", "Computer Vision", 9, "IISC-CSA"),
    ("R009", "Sneha Reddy", "Healthcare Informatics", 5, "VIT-SITE"),
    ("R010", "Rohan Das", "Machine Learning", 11, "IITKGP-CSE"),
    ("R011", "Meera Nair", "Artificial Intelligence", 14, "TCS-AILAB"),
    ("R012", "Aditya Joshi", "Deep Learning", 6, "IITD-CSE"),
    ("R013", "Kavya Krishnan", "Natural Language Processing", 4, "IITM-CSE"),
    ("R014", "Siddharth Bose", "Computer Vision", 8, "IITB-EE"),
    # --- Graph / data cluster ---
    ("R015", "Deepak Verma", "Graph Databases", 7, "VIT-SCOPE"),
    ("R016", "Pooja Mishra", "Social Network Analysis", 6, "IIITH-CSE"),
    ("R017", "Amit Chauhan", "Information Retrieval", 13, "IITD-CSE"),
    ("R018", "Lakshmi Pillai", "Data Science", 5, "IITM-DSAI"),
    ("R019", "Harsh Agarwal", "Graph Databases", 8, "BITS-CSIS"),
    ("R020", "Divya Saxena", "Database Systems", 10, "NITT-CSE"),
    ("R021", "Manish Tiwari", "Social Network Analysis", 7, "IITKGP-CSE"),
    ("R022", "Shreya Kapoor", "Information Retrieval", 4, "IISC-CSA"),
    ("R023", "Nikhil Bhat", "Database Systems", 3, "VIT-SCOPE"),
    # --- Security cluster ---
    ("R024", "Farhan Qureshi", "Network Security", 9, "IIITH-SEC"),
    ("R025", "Ishita Banerjee", "Cryptography", 12, "IIITH-SEC"),
    ("R026", "Varun Malhotra", "Cybersecurity", 6, "VIT-SITE"),
    ("R027", "Tanvi Kulkarni", "Network Security", 5, "NITT-CSE"),
    ("R028", "Gaurav Sinha", "Cryptography", 15, "IITD-MATH"),
    ("R029", "Ritu Choudhary", "Cybersecurity", 7, "BITS-CSIS"),
    ("R030", "Sameer Khan", "Cybersecurity", 8, "IITKGP-CSE"),
    # --- Cloud / distributed cluster ---
    ("R031", "Prakash Hegde", "Distributed Systems", 16, "IISC-CSA"),
    ("R032", "Swati Deshmukh", "Cloud Computing", 6, "VIT-SCOPE"),
    ("R033", "Arvind Raman", "Distributed Systems", 12, "IITM-CSE"),
    ("R034", "Nisha Jain", "Cloud Computing", 8, "TCS-AILAB"),
    ("R035", "Kunal Shah", "Distributed Systems", 5, "IITB-CSE"),
    ("R036", "Bhavna Arora", "Cloud Computing", 7, "NITT-CSE"),  # deliberately has no co-authors
    # --- Bridge researchers connecting the clusters ---
    ("R037", "Sanjay Mehta", "Artificial Intelligence", 18, "IITD-CSE"),
    ("R038", "Rekha Venkatesh", "Machine Learning", 13, "IISC-CDS"),
    ("R039", "Omkar Patil", "Distributed Systems", 9, "VIT-SITE"),
    ("R040", "Zoya Hussain", "Database Systems", 10, "TCS-AILAB"),
]

# ---------------------------------------------------------------- Papers
# (paperId, title, publicationYear, abstract, [authors in order], [topicIds], venueId or None, [cited paperIds])
# venueId starting with "C" -> PRESENTED_AT a Conference, "J" -> PUBLISHED_IN a Journal.
PAPERS = [
    # --- Review-1 sample papers (titles/years kept exactly) ---
    ("P001", "Graph-Based Recommendation Systems", 2025,
     "Models users, items and their interactions as a property graph and ranks recommendations with path-based similarity.",
     ["R001", "R002"], ["T004", "T002"], "C003", ["P020", "P024", "P026", "P030"]),
    ("P002", "Machine Learning for Healthcare", 2024,
     "Surveys supervised and unsupervised learning methods for diagnosis, triage and readmission prediction.",
     ["R003", "R009"], ["T002", "T015"], "J006", ["P007", "P011", "P015"]),
    ("P003", "Cyber Threat Detection Using AI", 2025,
     "Combines anomaly detection and supervised classifiers to detect cyber threats in enterprise telemetry.",
     ["R004", "R037"], ["T003", "T001"], "C006", ["P002", "P035", "P038", "P013"]),
    ("P004", "Graph Databases for Research Networks", 2026,
     "Shows how a Neo4j property graph supports collaboration discovery and citation analysis over research networks.",
     ["R002", "R015", "R019"], ["T004", "T013"], "J002", ["P001", "P005", "P023", "P024", "P029", "P028"]),
    ("P005", "Community Detection in Academic Networks", 2025,
     "Applies modularity-based community detection to co-authorship graphs to reveal research groups.",
     ["R016", "R021", "R002"], ["T013", "T004"], "C004", ["P026", "P030", "P025"]),
    # --- AI / ML ---
    ("P006", "Transformer Models for Clinical Text Classification", 2024,
     "Fine-tunes transformer encoders on discharge summaries to classify clinical conditions.",
     ["R007", "R009", "R003"], ["T007", "T015"], "J006", ["P007", "P017", "P011"]),
    ("P007", "Explainable Deep Learning for Medical Imaging", 2023,
     "Uses saliency and concept attribution to explain convolutional models for radiology images.",
     ["R008", "R009"], ["T006", "T008", "T015"], "J006", []),
    ("P008", "Federated Learning for Privacy-Preserving Healthcare Analytics", 2025,
     "Trains predictive models across hospitals without sharing raw patient records.",
     ["R001", "R009", "R010"], ["T002", "T015", "T005"], "C002", ["P002", "P015", "P016", "P013"]),
    ("P009", "Efficient Attention Mechanisms for Low-Resource Indic Languages", 2025,
     "Proposes sparse attention for language models trained on limited Indic-language corpora.",
     ["R007", "R013"], ["T007", "T006"], "C008", ["P006", "P017"]),
    ("P010", "Self-Supervised Representation Learning for Satellite Images", 2024,
     "Learns visual features from unlabeled satellite imagery with contrastive objectives.",
     ["R008", "R014"], ["T008", "T006"], "C001", ["P013", "P007"]),
    ("P011", "Reinforcement Learning for Adaptive Tutoring Systems", 2023,
     "Uses reinforcement learning to personalise exercise sequencing for students.",
     ["R005", "R011"], ["T001", "T002"], "J003", []),
    ("P012", "Benchmarking Large Language Models on Reasoning Tasks", 2025,
     "Evaluates large language models on arithmetic, logical and commonsense reasoning benchmarks.",
     ["R005", "R012", "R013"], ["T001", "T007"], "C002", ["P017", "P011", "P009"]),
    ("P013", "Continual Learning without Catastrophic Forgetting", 2024,
     "Introduces a replay-free regulariser that preserves earlier tasks while learning new ones.",
     ["R006", "R012"], ["T006", "T002"], "C001", ["P016"]),
    ("P014", "Robust Object Detection under Adverse Weather", 2025,
     "Improves detector robustness to fog, rain and low light with synthetic augmentation.",
     ["R014", "R006"], ["T008", "T006"], "C010", ["P010", "P013"]),
    ("P015", "AutoML Pipelines for Tabular Data", 2024,
     "Automates feature engineering, model selection and tuning for tabular datasets.",
     ["R010", "R003", "R018", "R001"], ["T002", "T005"], "C009", ["P011"]),
    ("P016", "Neural Architecture Search on Edge Devices", 2024,
     "Searches compact neural architectures under latency and memory budgets of edge hardware.",
     ["R006", "R010"], ["T006", "T002"], "J003", []),
    ("P017", "Knowledge-Grounded Dialogue Generation", 2024,
     "Grounds conversational responses in retrieved knowledge passages to reduce hallucination.",
     ["R011", "R007"], ["T007", "T001"], "J003", ["P011"]),
    ("P018", "Fairness-Aware Machine Learning for Credit Scoring", 2025,
     "Measures and mitigates demographic bias in credit-scoring classifiers.",
     ["R001", "R010", "R011"], ["T002", "T001", "T005"], "J001", ["P015", "P008", "P013"]),
    ("P019", "Multimodal Learning for Disease Prognosis", 2026,
     "Fuses imaging, clinical notes and lab values to predict disease progression.",
     ["R003", "R008", "R009"], ["T015", "T006", "T008"], "J006", ["P002", "P007", "P008", "P014", "P006"]),
    ("P020", "Graph Neural Networks for Molecular Property Prediction", 2024,
     "Applies message-passing neural networks to predict properties of molecular graphs.",
     ["R038", "R006"], ["T002", "T006", "T004"], "C001", ["P013", "P016"]),
    ("P021", "Knowledge Graph Embeddings for Link Prediction", 2025,
     "Compares translational and bilinear embeddings for predicting missing links in knowledge graphs.",
     ["R038", "R002", "R005"], ["T004", "T002", "T001"], "C003", ["P020", "P023", "P026"]),
    ("P022", "Large Language Models as Research Assistants", 2026,
     "Studies how language models help with literature review, summarisation and hypothesis generation.",
     ["R005", "R011", "R037"], ["T001", "T007"], "J001", ["P012", "P009", "P017", "P027"]),
    # --- Graph / data ---
    ("P023", "Scalable Property Graph Query Optimization", 2023,
     "Presents cost-based optimisation of pattern-matching queries on property graphs.",
     ["R002", "R020"], ["T004", "T011"], "J002", []),
    ("P024", "Cypher Query Performance on Large Citation Graphs", 2024,
     "Benchmarks Cypher traversals, indexes and query plans on citation graphs of increasing size.",
     ["R015", "R019", "R023"], ["T004", "T014"], "C005", ["P023", "P029"]),
    ("P025", "Author Name Disambiguation using Graph Features", 2024,
     "Resolves ambiguous author names with co-author and venue features from a bibliographic graph.",
     ["R017", "R022", "R016"], ["T014", "T013"], "C009", ["P031"]),
    ("P026", "Influence Maximization in Academic Social Networks", 2024,
     "Selects seed researchers that maximise information spread in academic social networks.",
     ["R016", "R021"], ["T013", "T005"], "J001", ["P030"]),
    ("P027", "Semantic Search over Scholarly Knowledge Graphs", 2025,
     "Combines dense retrieval with knowledge-graph structure for scholarly search.",
     ["R017", "R022", "R038"], ["T014", "T004", "T007"], "C004", ["P025", "P021", "P031", "P024"]),
    ("P028", "Temporal Graph Analytics for Citation Dynamics", 2025,
     "Models how citation networks evolve over time and forecasts emerging topics.",
     ["R018", "R016", "R002"], ["T013", "T005", "T004"], "C003", ["P026", "P024", "P030"]),
    ("P029", "Benchmarking Graph Databases vs Relational Systems", 2023,
     "Compares multi-hop query latency of graph and relational databases on connected data.",
     ["R020", "R023", "R015"], ["T004", "T011"], "J002", ["P023"]),
    ("P030", "Link Prediction for Co-authorship Networks", 2024,
     "Predicts future collaborations from neighbourhood and path-based similarity measures.",
     ["R021", "R018"], ["T013", "T002"], "C009", ["P031"]),
    ("P031", "Entity Resolution in Bibliographic Databases", 2023,
     "Deduplicates paper and author records across bibliographic sources.",
     ["R020", "R017"], ["T014", "T005"], "J001", []),
    ("P032", "Graph Partitioning for Distributed Graph Databases", 2025,
     "Partitions large graphs across machines to minimise cross-partition traversals.",
     ["R019", "R033", "R040"], ["T004", "T011"], "C004", ["P023", "P029", "P046", "P049"]),
    ("P033", "Data Lakehouse Architectures for Research Analytics", 2025,
     "Designs a lakehouse that unifies batch and streaming research-analytics workloads.",
     ["R040", "R018", "R034"], ["T005", "T012"], "J001", ["P049", "P047", "P029"]),
    ("P034", "Query Recommendation for Graph Exploration", 2026,
     "Recommends next Cypher queries to users exploring an unfamiliar graph database.",
     ["R015", "R023", "R001"], ["T004", "T002"], "J002", ["P024", "P027", "P001", "P032"]),
    # --- Security ---
    ("P035", "Deep Learning-Based Intrusion Detection for IoT Networks", 2024,
     "Detects intrusions in IoT traffic with lightweight convolutional and recurrent models.",
     ["R024", "R027", "R037"], ["T009", "T006", "T003"], "C007", ["P013", "P042", "P044"]),
    ("P036", "Post-Quantum Lattice-Based Signature Schemes", 2023,
     "Analyses efficiency and security of lattice-based digital signature schemes.",
     ["R025", "R028"], ["T010"], "J004", []),
    ("P037", "Phishing Website Detection with Graph Features", 2025,
     "Builds a hyperlink graph of websites and classifies phishing pages using graph features.",
     ["R026", "R029", "R015"], ["T003", "T004"], "C006", ["P035", "P024", "P042"]),
    ("P038", "Ransomware Behaviour Analysis using Sandboxing", 2024,
     "Characterises ransomware families from dynamic behaviour captured in a sandbox.",
     ["R030", "R004"], ["T003"], "J005", ["P044"]),
    ("P039", "Zero-Knowledge Proofs for Credential Verification", 2025,
     "Lets users prove possession of academic credentials without revealing personal data.",
     ["R025", "R028", "R039"], ["T010", "T003"], "C006", ["P036", "P044"]),
    ("P040", "Adversarial Attacks on Network Intrusion Detectors", 2025,
     "Crafts adversarial traffic that evades learned intrusion detectors and evaluates defences.",
     ["R037", "R024", "R012"], ["T003", "T009", "T002"], "J004", ["P035", "P013", "P042"]),
    ("P041", "Secure Multi-Party Computation for Healthcare Data", 2026,
     "Enables joint statistics over hospital datasets without disclosing individual records.",
     ["R028", "R009", "R025"], ["T010", "T015"], "J004", ["P036", "P039", "P002"]),
    ("P042", "Botnet Detection using Traffic Flow Graphs", 2024,
     "Represents network flows as graphs and detects botnet communities within them.",
     ["R027", "R024"], ["T009", "T013"], "J005", ["P026"]),
    ("P043", "Threat Intelligence Knowledge Graphs", 2026,
     "Integrates indicators of compromise, malware and actors into a queryable knowledge graph.",
     ["R004", "R026", "R019"], ["T003", "T004"], "J005", ["P037", "P038", "P040", "P021", "P003"]),
    ("P044", "Side-Channel Resistant Implementations of AES", 2023,
     "Evaluates masking countermeasures that protect AES implementations against power analysis.",
     ["R028", "R029"], ["T010", "T003"], "J004", ["P036"]),
    ("P045", "Anomaly Detection in Authentication Logs", 2025,
     "Flags suspicious login behaviour using sequence models over authentication logs.",
     ["R029", "R030", "R004"], ["T003", "T002"], "J005", ["P038", "P035"]),
    # --- Cloud / distributed ---
    ("P046", "Consensus Protocols for Geo-Distributed Databases", 2023,
     "Compares Paxos- and Raft-based replication across geographically distributed data centres.",
     ["R031", "R033"], ["T011"], "J002", []),
    ("P047", "Serverless Workflow Scheduling", 2024,
     "Schedules multi-step serverless workflows to reduce cold starts and cost.",
     ["R032", "R034"], ["T012", "T011"], None, ["P046"]),
    ("P048", "Autoscaling Microservices with Reinforcement Learning", 2025,
     "Learns autoscaling policies for microservices that balance latency targets and cost.",
     ["R034", "R035", "R011"], ["T012", "T002"], "C002", ["P047", "P011", "P049"]),
    ("P049", "Fault-Tolerant Stream Processing at Scale", 2024,
     "Provides exactly-once stream processing with low-overhead checkpointing.",
     ["R033", "R035", "R031"], ["T011", "T012"], "C005", ["P046"]),
    ("P050", "Secure Container Orchestration in Multi-Tenant Clouds", 2025,
     "Hardens container orchestration against cross-tenant attacks in shared clusters.",
     ["R039", "R032", "R024"], ["T012", "T003", "T009"], "C006", ["P047", "P035", "P046"]),
    ("P051", "Energy-Efficient Resource Allocation in Data Centres", 2024,
     "Allocates virtual machines to minimise energy use while meeting service-level objectives.",
     ["R036"], ["T012"], None, ["P047"]),
    ("P052", "Byzantine Fault Tolerance for Permissioned Blockchains", 2025,
     "Improves throughput of Byzantine fault-tolerant consensus for permissioned ledgers.",
     ["R039", "R031", "R025"], ["T011", "T010"], "J004", ["P046", "P036", "P039"]),
    ("P053", "Cost-Aware Query Processing in Cloud Data Warehouses", 2026,
     "Optimises warehouse queries for monetary cost as well as latency.",
     ["R040", "R020", "R032"], ["T012", "T005", "T011"], "J002", ["P033", "P049", "P032", "P023"]),
    ("P054", "Edge-Cloud Continuum for Real-Time Analytics", 2025,
     "Places analytics operators across edge and cloud tiers to meet real-time deadlines.",
     ["R035", "R040"], ["T012", "T005"], "C003", ["P049", "P047", "P033"]),
    ("P055", "Collaborative Filtering on Heterogeneous Academic Graphs", 2026,
     "Recommends collaborators and papers using meta-paths over heterogeneous academic graphs.",
     ["R001", "R038", "R021"], ["T002", "T004", "T013"], "J001", ["P001", "P021", "P030", "P028", "P018"]),
]

# COLLABORATED_WITH pairs stated explicitly in Review-1 (Alice<->Rahul, Alice<->Priya, Rahul<->Neha).
# They are also backed by co-authored papers (P001, P015, P021), so seed.py marks them
# source = "co-authorship"; they are listed here so the validator can check they exist.
REVIEW_COLLABORATIONS = [("R001", "R002"), ("R001", "R003"), ("R002", "R005")]

# Example relationships from Review-1 that the validator asserts.
REVIEW_EXAMPLES = {
    "AUTHORED": [("R001", "P001"), ("R002", "P001"), ("R003", "P002")],
    "WORKS_AT": [("R001", "VIT"), ("R002", "IIT Madras")],
    "HAS_TOPIC": [("P001", "Graph Databases"), ("P002", "Machine Learning")],
    "CITES": [("P004", "P001"), ("P003", "P002")],
}


def doi_for(paper_id: str, year: int) -> str:
    return f"10.5555/acn.{year}.{paper_id.lower()}"


def email_for(name: str, domain: str) -> str:
    return f"{name.lower().replace(' ', '.')}@{domain}"


def role_for(experience_years: int) -> str:
    if experience_years >= 15:
        return "Professor"
    if experience_years >= 10:
        return "Associate Professor"
    if experience_years >= 6:
        return "Assistant Professor"
    return "Research Scientist"
