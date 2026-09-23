"""VeriScan legal templates — Terms of Service and Privacy Policy.

Reviewed by the maintainer; not legal advice. Templates aim to minimise the legal
exposure of the app owner, publisher and developer. Update before public launch.
"""
from datetime import datetime, timezone

TERMS_VERSION = "1.0.0"
PRIVACY_VERSION = "1.0.0"
EFFECTIVE_DATE = "1 January 2026"


TERMS_OF_SERVICE = f"""# VeriScan — Terms of Service

**Version {TERMS_VERSION} · Effective {EFFECTIVE_DATE}**

## 1. Acceptance
By tapping "I agree" during signup, using the VeriScan mobile app, or otherwise accessing our services (collectively, the "Services"), you enter into a legally binding agreement with the operator of VeriScan ("we", "us", "our"). If you do not agree with any part of these Terms, you must not use the Services.

## 2. Not medical, dietary or professional advice
VeriScan is an **informational tool**. The safety scores, ingredient explanations, personalized match percentages, nutritional summaries and product alternatives are generated automatically from public data sources and internal heuristics. They are **not medical, dietary, cosmetic, veterinary, pharmaceutical or professional advice**. Never rely on VeriScan to diagnose, treat, cure or prevent any disease, allergy or condition. Always read the physical product label and consult a qualified healthcare or nutrition professional before making purchasing, dietary or health decisions, especially if you are pregnant, nursing, treating a medical condition or managing an allergy.

## 3. Data sources and accuracy
Product records, ingredient lists, nutritional data and images may originate from public registries (including but not limited to Open Food Facts and Open Beauty Facts), user contributions, or third-party APIs. We **do not guarantee** accuracy, completeness, currency, availability or fitness for any particular purpose of any product data, price, retailer link, ingredient explanation, safety score or match percentage. Product formulations change and public data may lag behind physical packaging. You use all such information at your own risk.

## 4. Intellectual property
- The VeriScan brand, app design, source code, safety-score algorithm, ingredient knowledge base, personal-match methodology and all original text and visuals are the exclusive property of the app operator and are protected by copyright, trademark and other laws.
- Third-party trademarks, product names, brand names, packaging photographs and logos referenced or displayed in the app remain the property of their respective owners. Reference to a product is descriptive and does not imply endorsement, sponsorship, or affiliation.
- Public-registry data is redistributed under the terms of its source licence (for example, Open Food Facts is available under the Open Database Licence). You may not scrape, resell, redistribute or otherwise commercially exploit our aggregated, curated, scored or personalized outputs without prior written permission.

## 5. User contributions
When you submit product photos, notes, corrections, ingredient text, misinformation reports or any other content ("Contributions"), you represent and warrant that (a) you own or have all necessary rights to the Contribution, (b) it does not infringe any third-party intellectual property, privacy or publicity rights, (c) it contains no unlawful, defamatory or misleading content, and (d) it is offered without expectation of compensation. You grant us a worldwide, perpetual, irrevocable, sub-licensable, royalty-free licence to host, store, reproduce, modify, publish, translate, distribute and display your Contribution in connection with the Services, including for training our automated systems and improving the product database.

## 6. Acceptable use
You must not (a) misuse the Services in a way that circumvents scan quotas, entitlements or purchases; (b) reverse-engineer, decompile or attempt to derive the source of the Services except as expressly permitted by law; (c) upload malware, spam, phishing content or hate speech; (d) impersonate another person or misrepresent your affiliation; (e) use the Services in violation of any applicable law, sanctions programme, export-control regime or third-party right.

## 7. Accounts and security
You must provide accurate contact information. You are responsible for maintaining the confidentiality of any password or one-time code. You must notify us immediately of any unauthorized use. We may suspend, restrict, or terminate any account at any time, with or without notice, for suspected abuse, fraud, chargeback, breach of these Terms or as required by law. We do not delete accounts by default — suspended accounts remain suspended and can be reactivated at our discretion.

## 8. Payments, quotas and refunds
Free scan quotas, promotional pricing, pay-per-scan credits and subscription plans are offered at our discretion and may change without prior notice. All amounts are shown at the time of purchase in the currency you select and are inclusive of applicable taxes only where explicitly indicated. Purchases are processed by third-party payment providers (e.g. Razorpay, Stripe, Apple, Google). We do not store card details. Except where required by law or the applicable app store, purchases are **non-refundable** once a scan credit has been consumed or a subscription period has begun. Store refunds must be requested through the store from which you purchased.

## 9. Third-party services and links
The app may link out to retailer marketplaces, payment providers, external data sources and other websites. We do not control these third parties and we accept no responsibility for their content, prices, privacy practices, availability or terms. Your use of a third-party service is governed by that service's own agreements.

## 10. Disclaimer of warranties
To the maximum extent permitted by law, the Services are provided **"as is" and "as available"**, without warranties of any kind, express or implied, including without limitation warranties of merchantability, fitness for a particular purpose, non-infringement, accuracy, uninterrupted availability, error-free operation, or any warranty arising from course of dealing or usage of trade. Some jurisdictions do not allow the exclusion of implied warranties, in which case some of these exclusions may not apply to you.

## 11. Limitation of liability
To the maximum extent permitted by law, in no event will the operator, its officers, directors, employees, contractors, agents, suppliers, licensors or partners be liable to you for any indirect, incidental, special, consequential, punitive, exemplary or aggravated damages of any kind, including without limitation loss of profits, revenue, data, business, goodwill or opportunity, arising out of or in connection with your use of the Services, even if advised of the possibility of such damages. Our total aggregate liability for any claim arising out of or in connection with the Services, regardless of the form of action, is limited to the greater of (a) the total amount you paid to us in the twelve (12) months immediately preceding the claim, or (b) fifty (50) United States dollars.

## 12. Indemnity
You will indemnify, defend and hold harmless the operator and its affiliates, officers, employees, contractors and agents from and against any and all claims, damages, obligations, losses, liabilities, costs and expenses (including reasonable attorneys' fees) arising from or related to (a) your access to or use of the Services, (b) your Contributions, (c) your violation of these Terms, or (d) your violation of any third-party right, including any intellectual-property, privacy, publicity or contract right.

## 13. Governing law and dispute resolution
These Terms are governed by the laws of the operator's principal place of business, excluding its conflict-of-laws rules. Any dispute, claim or controversy arising out of or relating to these Terms or the Services will be finally resolved by binding arbitration on an individual basis (no class actions) in accordance with the arbitration rules applicable at the seat of the operator. Where mandatory local consumer-protection law grants you additional or different rights, those rights apply notwithstanding this Section 13.

## 14. Changes to these Terms
We may update these Terms from time to time. The current version is always available inside the app. Continued use of the Services after an update constitutes acceptance of the updated Terms. If a change materially reduces your rights, we will make reasonable effort to notify you in-app or by email.

## 15. Contact
Questions? Reach us through the in-app Support screen.
"""


PRIVACY_POLICY = f"""# VeriScan — Privacy Policy

**Version {PRIVACY_VERSION} · Effective {EFFECTIVE_DATE}**

## 1. Overview
This Privacy Policy explains how the operator of VeriScan ("we", "us", "our") collects, uses, shares and protects information when you use the VeriScan mobile app and related services (the "Services"). Please read it alongside our Terms of Service.

## 2. Information we collect
We collect only what we need to operate the app.
- **Account identifier**: email address or phone number and a hashed password (never stored in plaintext).
- **Preferences**: your dietary preferences, health targets and ingredient sensitivities.
- **Usage**: barcodes you scan, product-detail views, contributions, watchlist entries, support tickets and misinformation reports, timestamps, entitlement counters, and coarse device / language information.
- **Guest fingerprint**: a random device identifier stored securely on-device to track free guest scans before signup.
- **Payments metadata**: purchase records (tier, amount, timestamp). Card and account details are handled by our payment providers; we do not store them.
- **Optional contributions**: photos of product labels you submit for the community database.

We do **not** ask for date of birth, government ID, precise location, biometrics, contacts, calendars or health-record data.

## 3. How we use information
- Provide the app: authenticate you, enforce quotas, compute scores and matches, deliver support responses, enable password reset.
- Improve the app: aggregate, anonymized analytics to improve ingredient scoring and product coverage.
- Legal and safety: fraud prevention, abuse detection, chargeback disputes, enforcing our Terms.
- Communications: transactional email such as password-reset OTPs and watchlist alerts. We do not use your data for third-party advertising or sell it to data brokers.

## 4. Legal bases (EEA / UK users)
Our processing relies on (a) performance of the contract with you (running your account), (b) our legitimate interests (fraud prevention, product improvement), (c) your consent (optional communications, contributions), and (d) legal obligations where they apply.

## 5. Sharing
We share information only with:
- **Payment providers** (Razorpay, Stripe, and app-store billing) to process purchases.
- **Public-data providers** (Open Food Facts, Open Beauty Facts) when we query barcodes; we send the barcode only, never account identifiers.
- **Email provider** (Emergent-managed Resend) to deliver transactional emails.
- **Automated language-model providers** (Anthropic Claude via Emergent) to extract structured data from optional contribution photos you upload.
- **Legal authorities** where required by law, court order or legitimate legal process.
- **Successors** if we merge, are acquired, or transfer the Service to a successor operator, subject to this Privacy Policy.

## 6. Retention
- Scan history, preferences and watchlist entries are retained while your account is active.
- Support tickets and misinformation reports are retained for up to 24 months for quality control.
- Guest-mode data is retained on-device only.
- We do not hard-delete user records: on account closure, records are marked as deleted and retained in aggregate/anonymized form for legal and security purposes.

## 7. Security
We apply industry-standard controls: TLS 1.2+ in transit, bcrypt-hashed passwords, secure device storage (Keychain / EncryptedSharedPreferences) for auth tokens and guest IDs, least-privilege database access, and application-level authorization on every route. No system is perfectly secure — you must also keep your device and password safe.

## 8. Your rights
Depending on your jurisdiction (including DPDP Act 2023 in India, GDPR in the EU/UK, CCPA in California and similar laws), you may have the right to access, correct, port or delete your personal data, restrict or object to processing, and withdraw consent. You can exercise these rights through the in-app Support screen. We will respond within the timeframe required by your applicable law.

## 9. Children
The Services are not directed to children under 13 (or the equivalent age in your jurisdiction). If we learn that we have collected personal data from a child without appropriate consent, we will delete it promptly.

## 10. International transfers
Our infrastructure may process data in India, the European Union, the United States or elsewhere. Where required, we use standard contractual clauses or equivalent safeguards.

## 11. Changes
We will notify material changes in-app or by email. Continued use after a change constitutes acceptance.

## 12. Contact
Reach us through the in-app Support screen or the email address published in your app store listing.
"""
