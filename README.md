# Axiom Equilibrium Engine 🛡️
> **Production-Grade Non-Linear Credit Scoring for the Next Billion Users**

Axiom is a high-fidelity credit scoring platform designed for thin-file users. It leverages **Account Aggregator (AA)** data, **Spatio-Temporal Graph Neural Networks (GNNs)**, and **SHAP-inspired Interpretability** to transform raw transaction streams into risk-aware credit profiles.

---

## Architecture: The Equilibrium Engine

Axiom has evolved from a linear additive model into a **non-linear, risk-aware probabilistic engine**. The architecture is designed for **Ephemeral Stateless Execution**, ensuring zero-footprint memory isolation after each scoring run.

### Core Components:
1.  **Ingestion & Entropy**: Shannon Entropy analysis of transaction diversity and time-decayed risk signal extraction.
2.  **Neighborhood Graph (KDTree)**: Projection of transactions into UTM space for geospatial trust density validation.
3.  **GNN Reputation Propagation**: An ST-PIGNN (Spatio-Temporal Physics-Informed GNN) that propagates trust from **Reference Nodes** (Verified Students, Parents, Landlords) to the user.
4.  **Probabilistic Ensemble**: A non-linear fusion layer that uses Sigmoid scaling to polarize scores, creating clear variance between Prime and Subprime tiers.

---

## The Stateless Workflow (End-to-End)

The pipeline executes a 7-stage ephemeral workflow:

1.  **Ingestion**: Statement ingestion via `StatementIngestor`.
2.  **Risk Analysis**: Identification of "Red Flag" keywords with **Temporal Decay** (recent risks carry higher penalties).
3.  **Merchant Resolution**: Multi-stage resolution via web search and GSTIN validation.
4.  **Entropy & Diversity**: Calculation of merchant diversity scores (Shannon Entropy).
5.  **Spatial Enrichment**: KDTree-based neighborhood density calculation.
6.  **Graph Injection**: Propagation of reputation scores from linked Parent/Landlord VPAs into the GNN.
7.  **Ensemble Scoring**: Final calculation of the Axiom Score (300-900) with SHAP explainability.

---

## Scoring Logic: Non-Linear Probabilistic Model

The **Equilibrium Engine** eliminates "clumping" by using a polar scoring system.

### 1. The Base Formula
The score is derived from three primary signals:
$$Score = 300 + 600 \times \sigma(0.5 S_B + 0.35 S_T - 0.15 R_F)$$

*   **$S_B$ (Behavioral Discipline)**: Utility payment consistency and neighborhood integration.
*   **$S_T$ (Transitive Trust)**: Reputation inherited from the graph (Parent/Landlord links).
*   **$R_F$ (Red Flags)**: Negative behavioral signals (Betting, Cash-out, etc.).
*   **$\sigma$ (Sigmoid)**: Polarizes scores to create a spread from 350 to 850.

### 2. Specialized Nuances
*   **Student Safety Net**: Dampens negative $S_T$ impact by **0.3x** if the user is a verified student, protecting them from risky parental links.
*   **Institutional Landlord Anchor**: Adds **+80 points** for verified institutional landlords; applies a **-50 point** penalty if missing or low-trust.
*   **Proxy Anchor**: If no fixed income (Salary) is detected, the score is capped at **720** to prevent over-extension.
*   **Confidence Gating**: Scores are capped at **650** if the signal density is below 60%.

### 3. Interpretability (SHAP + AI Advisor)
Every score is accompanied by a **SHAP Waterfall Report** showing exactly how many points each signal added or subtracted. This data is fed into a **Gemini-powered AI Advisor** to provide targeted financial advice (e.g., "Shift spend to GST-verified pharmacies to boost your neighborhood score").

---

## Score Tiers

| Tier | Range | Interpretation |
|------|-------|-----------------|
| **Subprime** | 300-500 | High risk; building phase |
| **Standard** | 500-650 | Moderate risk; gated by data density |
| **High** | 650-800 | Low risk; Prime eligible with Anchors |
| **Prime** | 800-900 | Elite trust; verified by Salary + Institutional Anchors |

---

## Data Sources & Consent Flow

### 1. Account Aggregator (RBI-Regulated)

```
User Initiates AA Consent
    ↓
FIU (Fintech as User) → RBI → FIP (Bank)
    ↓
Bank Returns Encrypted Consented Data
    ↓
Axiom Decrypts with FIU Private Key
    ↓
Extract: Transactions, Balances, Metadata
```

**Supported FIPs:**
- SBI, HDFC Bank, ICICI Bank, Axis Bank, Kotak Bank, etc.
- See [Sahamati FIP Registry](https://sahamati.org.in)

### 2. Direct UPI Entry (Sandbox Mode)

Users can directly input UPI IDs for testing:
- Format: `username@bankcode`
- Example: `john.doe@okhdfcbank`
- Mock transaction data is generated for scoring validation

### 3. Phone Number → Bank Account Mapping

For users without AA consent, Axiom can fetch linked bank accounts via phone number:
- Uses National Payment Corporation of India (NPCI) IFSC database
- Async lookup via phone number registered with bank
- Requires user consent screen

---

## Additional Utilities

### WiFi and Electricity Bills
- **WiFi Bills**: Tracks payment consistency for broadband services.
- **Electricity Bills**: Monitors timely payments to DISCOMs for household electricity usage.

### Neighborhood Merchants
- **Merchant Density Analysis**: Evaluates the density of merchants in the user's neighborhood.
- **Merchant Trust Score**: Assigns scores based on transaction history and reliability of local merchants.

These utilities enhance the scoring model by incorporating additional behavioral and geospatial data.

---

## Environment Variables

Create `.env` file based on `.env.example`:

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `APP_NAME` | string | No | "axiom-credit" | Application name |
| `APP_ENV` | string | No | "development" | Environment (development, staging, production) |
| `DEBUG` | bool | No | True | Enable debug logging |
| `LOG_LEVEL` | string | No | "INFO" | Logging level |
| `SETU_AA_API_KEY` | string | Yes | - | Setu AA SDK API key |
| `SETU_AA_SECRET` | string | Yes | - | Setu AA SDK secret |
| `SETU_AA_BASE_URL` | string | No | "https://sandbox.setu.co" | Setu sandbox URL |
| `DATABASE_URL` | string | Yes | - | PostgreSQL connection URL |
| `MONGODB_URL` | string | Yes | - | MongoDB connection URL |
| `REDIS_URL` | string | No | "redis://localhost:6379/0" | Redis connection URL |
| `JWT_SECRET` | string | Yes | - | JWT signing secret (minimum 32 chars) |
| `JWT_ALGORITHM` | string | No | "HS256" | JWT algorithm |
| `AXIOM_MAX_TENANTS_PER_LANDLORD` | int | No | 3 | Threshold for herd check |
| `AXIOM_UTILITY_PAYMENT_DELTA_THRESHOLD` | int | No | 5 | Max days late before penalty |
| `AXIOM_CONFIDENCE_SIGNAL_THRESHOLD` | int | No | 20 | Min signals for high confidence |
| `TORCH_SEED` | int | No | 42 | Random seed for reproducibility |
| `REDIS_CACHE_TTL` | int | No | 3600 | Cache TTL in seconds |

---

## Module Documentation

### ingestion/
Retrieves and normalizes user financial data:
- **aa_client.py**: Setu AA API integration with RBI consent flow
- **upi_parser.py**: Extract recurring patterns and Khata proxy detection
- **utility_tracker.py**: Bill payment discipline scoring
- **rent_verifier.py**: Match UPI transfers to rent agreements

### graph/
Constructs trust graph and applies spatial-temporal GNN:
- **trust_graph.py**: NetworkX DiGraph of users, landlords, merchants
- **kdtree_enricher.py**: Geospatial merchant/utility enrichment
- **gineconv_model.py**: Graph neural network spatial layer
- **gru_temporal.py**: Sequential behavior modeling
- **st_pignn.py**: Full ST-PIGNN with constraint layer

### scoring/
Ensemble credit scoring with explainability:
- **baseline_score.py**: XGBoost/CatBoost baseline (S_B)
- **trust_transitive.py**: PageRank + landlord trust (S_T)
- **fraud_detector.py**: Loop + Sybil detection (R_F)
- **ensemble.py**: Combine scores → 300-900 range
- **shap_explainer.py**: Reason codes for regulatory output

### api/
FastAPI REST endpoints and middleware:
- **main.py**: App entry point, middleware, lifespan
- **routes/score.py**: POST /v1/score endpoint
- **routes/verify.py**: POST /v1/verify endpoint
- **schemas.py**: Pydantic v2 request/response models
- **cache.py**: Redis caching layer

### storage/
Persistence to PostgreSQL & MongoDB:
- **models.py**: SQLAlchemy ORM (UserProfile, AxiomScoreHistory, VerificationRecord)
- **events.py**: MongoDB document schemas for audit trails
- **migrations/**: Alembic version control

---

## Development

### Code Quality

```bash
# Format code
black .
isort .

# Lint
ruff check .

# Type check
mypy .

# Run tests with coverage
pytest tests/ -v --cov --cov-report=html
```

### Adding New Scoring Features

1. Create new class in `scoring/` inheriting from `BaseScorerMixin`
2. Implement `.score()` and `.explain()` methods
3. Add to `AxiomEnsemble.compute_final_score()` with weight
4. Write tests in `tests/test_scoring.py`
5. Update README documentation

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add new column"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Deployment

### Production Checklist

- [ ] Set `APP_ENV=production` and `DEBUG=False`
- [ ] Generate strong `JWT_SECRET` (32+ chars)
- [ ] Configure PostgreSQL with SSL
- [ ] Enable Redis persistence
- [ ] Set up log aggregation (ELK, DataDog)
- [ ] Configure rate limiting & DDoS protection
- [ ] Enable CORS only for trusted domains
- [ ] Set up monitoring & alerting
- [ ] Run penetration testing
- [ ] Document SLA & incident response

### Docker Build

```bash
docker build -t axiom-credit:latest .
docker run -p 8000:8000 --env-file .env axiom-credit:latest
```

---

## Compliance & Regulations

### RBI Account Aggregator Regulations
- All user data flows through RBI-regulated FIA (Financial Information Aggregator)
- User consent is mandatory and auditable
- Data is encrypted end-to-end
- See [RBI AA Framework](https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=47340)

### NPCI UPI Specifications
- Transaction data conforms to NPCI UPI 2.0 standards
- P2P and merchant payments are normalized

### Data Protection (DPDP Act 2023)
- User data is pseudonymized (phone/email hashed)
- Retention policy: 7 years for credit history
- Users can request data deletion (right to be forgotten)
- Audit trails logged to MongoDB

---

## Troubleshooting

### "Connection refused" on startup
- Ensure Docker containers are running: `docker-compose ps`
- Check logs: `docker-compose logs api`

### "JWT validation failed"
- Verify `JWT_SECRET` is set in `.env`
- Check token hasn't expired (tokens valid for 24h by default)

### "No transactions found for UPI"
- Verify UPI ID format: `username@bankcode`
- Check AA consent is valid and recent (< 30 days)
- For phone lookup, ensure bank account is linked

### "Score outside 300-900 range" (bug)
- This should never occur; file GitHub issue with user_id & timestamp
- Check logs for constraint layer violations

---

## Contributing

1. Fork repo
2. Create feature branch (`git checkout -b feat/new-scorer`)
3. Make changes with full test coverage
4. Run `black`, `ruff`, `mypy`
5. Submit PR with detailed description

---

## License

MIT

---

## Support

- **Docs**: [/docs/README.md](/docs/README.md)
- **Issues**: GitHub Issues
- **Email**: engineering@axiom.credit
