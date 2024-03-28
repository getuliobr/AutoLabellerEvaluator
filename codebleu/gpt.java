package org.jabref.gui;

import org.jabref.logic.l10n.Localization;
import org.jabref.model.entry.BibEntry;

import java.awt.Desktop;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;

public class MainTable {

    public void openExternalLink(BibEntry entry) {
        List<String> urls = entry.getFieldAsList("url");
        if (urls.size() == 1) {
            openSingleUrl(urls.get(0));
        } else {
            // Handle multiple URLs
            // Implement functionality to show popup menu for multiple URLs
        }
    }

    private void openSingleUrl(String url) {
        try {
            Desktop.getDesktop().browse(new URI(url));
        } catch (IOException | URISyntaxException e) {
            // Handle exception
            System.err.println("Error opening URL: " + e.getMessage());
        }
    }
}