// to run:
// node backend/server.js
const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = 3000;
const MORNING_REPORT_KEY = process.env.MORNING_REPORT_KEY

// Middleware
app.use(cors());
app.use(express.json());


// File paths
const projectsPath = path.join(__dirname, "../data/projects.json");
const historyPath = path.join(__dirname, "../data/history.json");
const activeBidsPath = path.join(__dirname, "../data/active-bids.json");


// Helper functions
function readJsonFile(filePath, defaultValue = []) {
    try {
        if (!fs.existsSync(filePath)) {
            return defaultValue;
        }

        const data = fs.readFileSync(filePath, "utf8");
        return JSON.parse(data);
    } catch (error) {
        console.error(`Error reading ${filePath}:`, error);
        return defaultValue;
    }
}

function writeJsonFile(filePath, data) {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 4));
}


app.use(express.static(path.join(__dirname, "../frontend")));

app.get("/", (req, res) => {
    res.sendFile(path.join(__dirname, "../frontend/index.html"));
});

app.get("/api/actions", (req, res) => {
    const actions = readJsonFile(path.join(__dirname, "../data/actions.json"));
    res.json(actions);
});

app.get("/api/estimators", (req, res) => {
    const estimators = readJsonFile(path.join(__dirname, "../data/estimators.json"));
    res.json(estimators);
});


// Get current projects
app.get("/api/projects", (req, res) => {
    try {
        const projects = readJsonFile(projectsPath);
        res.json(projects);
    } catch (error) {
        console.error("Error getting projects:", error);
        res.status(500).json({
            success: false,
            error: "Unable to load projects."
        });
    }
});

// Save current projects
app.post("/api/projects", (req, res) => {
    try {
        const projects = req.body;

        if (!Array.isArray(projects)) {
            return res.status(400).json({
                success: false,
                error: "Projects must be an array."
            });
        }

        writeJsonFile(projectsPath, projects);

        let activeBids = readJsonFile(activeBidsPath);

        projects.forEach(project => {
            if (project.bid === true) {
                const existingIndex = activeBids.findIndex(
                    job => job.jobNumber === project.jobNumber
                );

                if (existingIndex === -1) {
                    activeBids.push(project);
                } else {
                    activeBids[existingIndex] = {
                        ...activeBids[existingIndex],
                        ...project
                    };
                }
            }
        });

        writeJsonFile(activeBidsPath, activeBids);

        res.json({
            success: true,
            message: "Projects saved successfully.",
            projectCount: projects.length,
            activeBidCount: activeBids.length
        });
    } catch (error) {
        console.error("Error saving projects:", error);
        res.status(500).json({
            success: false,
            error: "Unable to save projects."
        });
    }
});

function requireMorningReportKey(req, res, next) {
    const key = req.headers["x-api-key"];

    if (!MORNING_REPORT_KEY || key !== MORNING_REPORT_KEY) {
        return res.status(401).json({
            success: false,
            error: "Unauthorized."
        });
    }

    next();
}

// Morning report
app.post("/api/morning-report", requireMorningReportKey, (req, res) => {
    try {
        const report = req.body;

        if (!report) {
            return res.status(400).json({
                success: false,
                error: "No report was provided."
            });
        }

        if (!Array.isArray(report.projects)) {
            return res.status(400).json({
                success: false,
                error: "Report must contain a projects array."
            });
        }

        const incomingProjects = report.projects;
        const history = readJsonFile(historyPath);
        let activeBids = readJsonFile(activeBidsPath);

        incomingProjects.forEach(project => {
            let existingHistoryIndex = -1;

            if (project.jobNumber) {
                existingHistoryIndex = history.findIndex(
                    job => job.jobNumber === project.jobNumber
                );
            }

            // Add new job to history
            if (existingHistoryIndex === -1) {
                history.push({
                    ...project,
                    firstReceived: project.received || new Date().toISOString(),
                    lastUpdated: new Date().toISOString()
                });
            } else {
                // Update existing job in history
                history[existingHistoryIndex] = {
                    ...history[existingHistoryIndex],
                    ...project,
                    lastUpdated: new Date().toISOString()
                };
            }

            // Add/update active bid
            if (project.bid === true) {
                const existingBidIndex = activeBids.findIndex(
                    job => job.jobNumber === project.jobNumber
                );

                if (existingBidIndex === -1) {
                    activeBids.push({
                        ...project
                    });
                } else {
                    activeBids[existingBidIndex] = {
                        ...activeBids[existingBidIndex],
                        ...project
                    };
                }
            }
        });

        writeJsonFile(historyPath, history);
        writeJsonFile(activeBidsPath, activeBids);
        writeJsonFile(projectsPath, incomingProjects);

        res.json({
            success: true,
            message: "Morning report saved successfully.",
            projectCount: incomingProjects.length,
            historyCount: history.length,
            activeBidCount: activeBids.length
        });
    } catch (error) {
        console.error("Morning report error:", error);

        res.status(500).json({
            success: false,
            error: "Failed to save morning report."
        });
    }
});

// Get history
app.get("/api/history", (req, res) => {
    try {
        const history = readJsonFile(historyPath);
        res.json(history);
    } catch (error) {
        console.error("Error getting history:", error);

        res.status(500).json({
            success: false,
            error: "Unable to load history."
        });
    }
});

// Get active bids
app.get("/api/active-bids", (req, res) => {
    try {
        const activeBids = readJsonFile(activeBidsPath);
        res.json(activeBids);
    } catch (error) {
        console.error("Error getting active bids:", error);

        res.status(500).json({
            success: false,
            error: "Unable to load active bids."
        });
    }
});

// Save active bids
app.post("/api/active-bids", (req, res) => {
    try {
        const activeBids = req.body;

        if (!Array.isArray(activeBids)) {
            return res.status(400).json({
                success: false,
                error: "Active bids must be an array."
            });
        }

        writeJsonFile(activeBidsPath, activeBids);

        res.json({
            success: true,
            message: "Active bids saved successfully.",
            bidCount: activeBids.length
        });
    } catch (error) {
        console.error("Error saving active bids:", error);

        res.status(500).json({
            success: false,
            error: "Unable to save active bids."
        });
    }
});

// Start server
console.log("Morning report key configured:", !!MORNING_REPORT_KEY);
app.listen(PORT,"0.0.0.0",  () => {
    console.log(`Server running at http://localhost:${PORT}`);
});

