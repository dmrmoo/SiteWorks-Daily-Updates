document.addEventListener("DOMContentLoaded", init);

async function init() {
    try {
        console.log("Starting app...");

        const projectsResponse = await fetch("/api/projects");
        console.log("Projects response:", projectsResponse.status);

        const projects = await projectsResponse.json();
        console.log("Projects:", projects);

        const actionsResponse = await fetch("/api/actions");
        console.log("Actions response:", actionsResponse.status);

        const actions = await actionsResponse.json();
        console.log("Actions:", actions);

        const estimatorsResponse = await fetch("/api/estimators");
        console.log("Estimators response:", estimatorsResponse.status);

        const estimators = await estimatorsResponse.json();
        console.log("Estimators:", estimators);

        console.log("Building table...");

        buildTable(projects, actions, estimators);

        console.log("Table built.");

        sendUpdates();

    } catch (error) {
        console.error("APP ERROR:", error);
    }
}

function buildTable(projects, actions, estimators) {

    const tbody = document.getElementById("projectBody");

    tbody.innerHTML = "";

    projects.forEach(project => {

        const row = document.createElement("tr");


        // Bid checkbox
        const bidCheckbox = document.createElement("input");

        bidCheckbox.type = "checkbox";

        bidCheckbox.checked = project.bid === true;


        // Action dropdown
        const actionSelect = document.createElement("select");

        actions.forEach(action => {

            const option = document.createElement("option");

            option.value = action;
            option.textContent = action;

            if (action === project.action) {
                option.selected = true;
            }

            actionSelect.appendChild(option);
        });


        // Assigned To multi-select
        const assignedContainer = document.createElement("div");

        assignedContainer.className = "assigned-container";


        // Allows both the old format:
        // "assigned": "Tony"
        //
        // and the new format:
        // "assigned": ["Tony", "Bruce"]

        let assignedPeople = [];

        if (Array.isArray(project.assigned)) {

            assignedPeople = project.assigned;

        } else if (project.assigned) {

            assignedPeople = [project.assigned];

        }


        estimators.forEach(person => {

            const label = document.createElement("label");

            label.className = "assigned-option";


            const checkbox = document.createElement("input");

            checkbox.type = "checkbox";

            checkbox.value = person;


            if (assignedPeople.includes(person)) {
                checkbox.checked = true;
            }


            label.appendChild(checkbox);

            label.appendChild(
                document.createTextNode(" " + person)
            );


            assignedContainer.appendChild(label);

        });


        // Regular table columns
        row.innerHTML = `
            <td>${project.jobNumber}</td>
            <td>${project.project}</td>
            <td>${project.gc}</td>
            <td>${project.type}</td>
            <td>${project.bidDue}</td>
        `;


        // Bid column
        const bidCell = document.createElement("td");

        bidCell.appendChild(bidCheckbox);


        // Action column
        const actionCell = document.createElement("td");

        actionCell.appendChild(actionSelect);


        // Assigned column
        const assignedCell = document.createElement("td");

        assignedCell.appendChild(assignedContainer);


        row.appendChild(bidCell);

        row.appendChild(actionCell);

        row.appendChild(assignedCell);


        tbody.appendChild(row);
    });
}


function sendUpdates() {

    const submit = document.getElementById("submit");

    submit.addEventListener("click", async () => {

        const rows = document.querySelectorAll("#projectBody tr");

        const updatedProjects = [];


        rows.forEach(row => {

            const cells = row.querySelectorAll("td");


            // Get all selected estimators
            const checkedPeople = cells[7].querySelectorAll(
                'input[type="checkbox"]:checked'
            );


            const assigned = [];


            checkedPeople.forEach(checkbox => {

                assigned.push(checkbox.value);

            });


            const project = {

                jobNumber: cells[0].textContent.trim(),

                project: cells[1].textContent.trim(),

                gc: cells[2].textContent.trim(),

                type: cells[3].textContent.trim(),

                bidDue: cells[4].textContent.trim(),

                bid: cells[5].querySelector("input[type='checkbox']").checked,

                action: cells[6].querySelector("select").value,

                assigned: assigned
            };


            updatedProjects.push(project);

        });


        try {

            const response = await fetch(
                "/api/projects",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify(updatedProjects)
                }
            );


            const result = await response.json();


            if (result.success) {

                alert("Projects saved successfully!");

            } else {

                alert("There was a problem saving the projects.");

            }


        } catch (error) {

            console.error("Save error:", error);

            alert("Unable to connect to the server.");

        }

    });
}
