const express = require('express');
const router = express.Router();
const containerPromise = require('../db');

// CREATE (POST) TEST
router.post('/', async (req, res) => {
    try {
        const container = await containerPromise; // Wait for Key Vault & DB connection
        const { name, email, title, description, priority, category } = req.body;
        
        const newTicket = {
            id: Date.now().toString(),
            name,
            email,
            title,
            description,
            priority: priority || "Medium",
            category: category || "General",
            status: "New",
            createdDate: new Date().toLocaleDateString('en-GB')
        };

        const { resource } = await container.items.create(newTicket);
        res.status(201).json({ success: true, data: resource });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

module.exports = router;
