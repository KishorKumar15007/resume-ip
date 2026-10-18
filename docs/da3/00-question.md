BACSE344 - Cloud Infrastructure and Architecture
Digital Assignment 3 Question
C1 Slot
Last date to submit in MSTeams: 30/10/2026

General instruction:
Continue with the same application you built and deployed in Digital Assignment 1 (hospital, institute, industry or any other domain). Every answer must be based on your own application and domain.

**Question 1 - Scale your application (5 marks)**
Your application's user base is about to grow sharply. Identify a realistic peak-demand situation for your own domain (for example, an outpatient rush in a hospital, results day at an institute, or a production shift change in a factory) and make your application handle it without downtime.

a) Describe your peak-demand situation and the API that will be hit hardest. Then run three instances of your backend using Docker Compose behind an Nginx load balancer, connected to your existing cloud database. Show that requests are distributed across all three instances. (1 mark)

b) Using Apache Bench or any suitable free load-testing tool (for example, hey, JMeter or k6), send 1,000 requests to that API, first with 1 instance and then with 3 instances, keeping the same tool and concurrency level for both runs. Tabulate requests per second and average response time, and state the improvement. (1.5 marks)

c) Stop one instance while the load test is running and record the failed requests. Then configure Nginx so that no request fails, and show the before-and-after count. (1.5 marks)

d) Draw the architecture diagram of your own implementation, using the actual names of your components: your frontend, the three backend containers and Nginx from part (a) (with their ports), your cloud database and hosting platform from Assignment 1, and the tools used (e.g., MongoDB Atlas, Render, Firebase). Then add the cloud bursting or edge/fog computing component to the same diagram, marked in a different colour, and explain how it would handle your peak-demand situation from part (a), and why you chose it for your domain. (1 mark)

**Question 2 - Secure your application (5 marks)**
Your application stores data about real people in your chosen domain. Secure it before it goes live.

a) Identify the most sensitive data your application stores (for example, patient records, student marks, or employee/production data). Store user passwords as salted hashes (bcrypt or Argon2) instead of plain text, and show a database screenshot before and after. (1 mark)

b) Add multi-factor authentication to login using a TOTP authenticator app (Google or Microsoft Authenticator). Restrict your Update and Delete APIs to logged-in users with the right role for your domain (for example, doctor, faculty, or supervisor), and show a request being rejected without a valid token. (1.5 marks)

c) Scan your application's Docker image with Trivy. Harden it (smaller base image, non-root user), rescan, and tabulate the CRITICAL and HIGH counts before and after. (1.5 marks)

d) Name two threat agents relevant to your domain. For each, state the control you implemented against it and one requirement from the regulation that applies to your application (HIPAA for health data, GDPR for personal data in general), with a reason why that regulation applies. (1 mark)

**What to submit**
- A report with screenshots, result tables for every part, and the GitHub link to an assignment-3 branch of your assignment 1 repository.
- A demo video of 3 minutes.

**Evaluation rubric**
The same scale applies to every part of both questions.
- Working, with screenshots/tables and a clear explanation: Full marks for that part
- Works, but evidence or explanation is missing or generic: Half marks
- Not attempted or not working: Zero
