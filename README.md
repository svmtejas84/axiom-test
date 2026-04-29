# Axiom Credit Scoring Platform

A production-grade Python monorepo implementing the **Axiom credit scoring platform** for thin-file users in India. Axiom combines Account Aggregator (AA) data, graph neural networks, and behavioral analysis to generate trustworthy credit scores in the 300-900 range for users with minimal historical credit records.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AXIOM CREDIT PLATFORM                        │
└─────────────────────────────────────────────────────────────────┘

                           ┌──────────────┐
                           │   FastAPI    │
                           │   REST API   │
                           └──────┬───────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
        ┌───────▼─────────┐  ┌────▼─────┐  ┌──────▼──────┐
        │  /v1/score      │  │/v1/verify │  │ /health     │
        │ (Main scoring)  │  │(Bilateral)│  │             │
        └────────┬────────┘  └────┬──────┘  └─────────────┘
                 │                │
    ┌────────────┴────────────────┴──────────┐
    │         INGESTION PIPELINE             │
    ├────────────────────────────────────────┤
    │ • Account Aggregator (Setu/Sahamati)   │
    │ • UPI Transaction Parser               │
    │ • Utility Bill Tracker (DISCOM, WiFi)  │
    │ • Rent Verification Engine             │
    │ • Phone Number → Bank Account Mapper   │
    └────────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │      GRAPH CONSTRUCTION            │
    ├────────────────────────────────────┤
    │ • TrustGraph (NetworkX DiGraph)     │
    │ • KDTree Node Enrichment            │
    │ • Feature Vector Assembly           │
    └────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │     NEURAL SCORING ENGINE          │
    ├────────────────────────────────────┤
    │ • GINEConv Spatial Layers (3x)      │
    │ • GRU Temporal Layers               │
    │ • ST-PIGNN Fusion + Constraints     │
    └────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────────────────┐
    │        SCORING ENSEMBLE (300-900)              │
    ├────────────────────────────────────────────────┤
    │ Score = 300 + 600 * [(0.5*S_B)                 │
    │                      + (0.35*S_T)              │
    │                      - (0.15*R_F)]             │
    │                                                │
    │ S_B: Baseline (XGBoost)                        │
    │ S_T: Transitive Trust (PageRank + Landlord)    │
    │ R_F: Fraud Risk (Loop Detection + Sybil)       │
    └────────────────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │      SHAP EXPLAINABILITY           │
    ├────────────────────────────────────┤
    │ • Top 3 Positive Drivers           │
    │ • Top 3 Negative Drivers           │
    │ • Reason Codes for Regulators      │
    └────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │       PERSISTENCE & CACHING        │
    ├────────────────────────────────────┤
    │ • PostgreSQL: Score History        │
    │ • MongoDB: Raw Behavioral Events   │
    │ • Redis: Real-time Score Cache     │
    └────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Setu AA API credentials (sandbox)

### 1. Clone & Setup Environment

```bash
cd axiom-credit
cp .env.example .env
# Edit .env with your Setu AA credentials and RBI sandbox URLs
```

### 2. Start Services

```bash
docker-compose up --build
```

This starts:
- **API**: FastAPI on `http://localhost:8000`
- **PostgreSQL**: Database on `localhost:5432`
- **MongoDB**: NoSQL store on `localhost:27017`
- **Redis**: Cache on `localhost:6379`

### 3. Health Check

```bash
curl http://localhost:8000/health
```

### 4. Score a User

**Method A: Consent Handle (from AA flow)**
```bash
curl -X POST http://localhost:8000/v1/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "consent_handle": "ch_1234567890",
    "include_reasons": true
  }'
```

**Method B: Enter UPI ID directly (mock consent)**
```bash
curl -X POST http://localhost:8000/v1/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "upi_id": "user@bankupi",
    "include_reasons": true
  }'
```

**Method C: Phone number → Bank Account lookup**
```bash
curl -X POST http://localhost:8000/v1/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "phone_number": "+919876543210",
    "include_reasons": true
  }'
```

### 5. Run Tests

```bash
pytest tests/ -v --cov
```

---

## API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | Service health & dependencies status |
| `/v1/score` | POST | JWT (stub) | Compute Axiom Score from AA data or UPI/phone |
| `/v1/verify` | POST | JWT (stub) | Bilateral landlord verification via signed agreement |

### POST /v1/score

**Request:**
```json
{
  "user_id": "uuid",
  "consent_handle": "ch_...",  // OR
  "upi_id": "user@bankupi",    // OR
  "phone_number": "+919876543210",
  "include_reasons": true
}
```

**Response (200 OK):**
```json
{
  "axiom_score": 650,
  "confidence_interval": 0.87,
  "tier": "High",
  "behavioral_drivers": [
    {
      "driver": "High Neighborhood Merchant Density",
      "impact_points": 42,
      "direction": "positive"
    },
    {
      "driver": "Inconsistent Utility Payment",
      "impact_points": -18,
      "direction": "negative"
    }
  ],
  "verification_status": "Bilateral Verified",
  "signal_count": 34,
  "generated_at": "2024-04-29T10:30:00Z"
}
```

### POST /v1/verify

**Request:**
```json
{
  "user_id": "uuid",
  "landlord_vpa": "landlord@bankupi",
  "agreement_hash": "sha256_hash_of_signed_agreement"
}
```

**Response (200 OK):**
```json
{
  "is_verified": true,
  "months_consistent": 8,
  "trust_coefficient": 0.92,
  "verification_timestamp": "2024-04-29T10:30:00Z"
}
```

---

## Credit Scoring Formula

### Final Axiom Score: 300-900 Range

```
AxiomScore = 300 + 600 * RawScore

where RawScore = (0.5 × S_B) + (0.35 × S_T) - (0.15 × R_F)

  S_B (Baseline, 50%):
    - XGBoost model trained on tabular features
    - Features: income volatility, expense ratio, utility discipline, rent consistency
    - Output: [0, 1]

  S_T (Transitive Trust, 35%):
    - Landlord's Axiom score × rent_verification_trust_coefficient
    - Plus PageRank centrality from transaction graph
    - Output: [0, 1]

  R_F (Fraud Risk, -15%):
    - Loop detection: flags circular transaction patterns (Sybil risk)
    - Herd check: flags landlords with >N tenants in same pincode
    - Output: [0, 1]
```

### Score Tiers

| Tier | Range | Interpretation |
|------|-------|-----------------|
| Low | 300-450 | High risk; limited lending eligibility |
| Medium | 450-600 | Moderate risk; eligible with guarant |
| High | 600-800 | Low risk; standard lending terms |
| Prime | 800-900 | Excellent risk; premium rates available |

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
