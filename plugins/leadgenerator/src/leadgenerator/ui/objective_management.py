"""Objective editing and scheduling controls embedded in the native workspace."""

OBJECTIVE_MANAGEMENT_JS = r"""
      const splitLines = value => String(value||"").split("\n").map(row=>row.trim()).filter(Boolean);
      const scheduleLabels = {active:"Activée dans Codex",paused:"En pause dans Codex",pending:"En attente de synchronisation",not_configured:"Non activée"};
      function canCallLeadTool() {
        const bridge=window.leadGeneratorMcpApp;
        return typeof window.openai?.callTool === "function" || (bridge?.connected && (!bridge.hostCapabilities || Boolean(bridge.hostCapabilities.serverTools)));
      }
      async function callLeadTool(name,args) {
        const result = typeof window.openai?.callTool === "function"
          ? await window.openai.callTool(name,args)
          : await window.leadGeneratorMcpApp.request("tools/call",{name,arguments:args},60000);
        if(result?.isError) throw new Error((result.content||[]).filter(row=>row.type==="text").map(row=>row.text).join("\n")||"Enregistrement impossible.");
        if(result?.structuredContent) return result.structuredContent;
        if(result?.structured_content) return result.structured_content;
        const text=(result?.content||[]).find(row=>row.type==="text")?.text;
        if(text) { try { return JSON.parse(text); } catch { throw new Error(text); } }
        return result;
      }
      function rememberObjective(objective) {
        const id=objective.objective_id;
        if(!id) throw new Error("L'objectif enregistré n'a pas été retourné.");
        data.objectives=objectives().map(row=>row.objective_id===id?objective:row);
      }
      function field(name,label,value,{required=false,multiline=true}={}) {
        const id=`objective-${name}`;
        return `<label for="${id}">${esc(label)}</label>${multiline
          ? `<textarea id="${id}" name="${name}" rows="3" ${required?"required":""}>${esc(value)}</textarea>`
          : `<input id="${id}" name="${name}" type="text" value="${esc(value)}" ${required?"required":""}>`}`;
      }
      async function editObjective(id,focusDocuments=false) {
        const target=document.getElementById("view");
        let objective=objectives().find(row=>(row.objective_id||row.id)===id);
        try {
          if(canCallLeadTool()) { objective=await callLeadTool("get_lead_objective",{objective_id:id});rememberObjective(objective); }
          if(!objective) throw new Error("Objectif introuvable. Rechargez la vue.");
          showObjectiveEditor(target,objective,focusDocuments);
        } catch(error) {
          const feedback=document.createElement("p");feedback.className="form-feedback error";feedback.setAttribute("role","alert");feedback.textContent=error.message;target.prepend(feedback);
        }
      }
      function showObjectiveEditor(target,objective,focusDocuments=false) {
        const id=objective.objective_id||objective.id,agent=objective.agent||{};
        const documents=objective.documents||agent.documents||[],notes=objective.notes||[];
        const listValue=value=>Array.isArray(value)?value.join("\n"):value||"";
        target.innerHTML=`<div class="section-head"><div><h2>Modifier l'objectif</h2><span class="hint">${esc(objective.name)} · objectif v${objective.revision||1} · agent v${agent.revision||1}</span></div><button class="button" data-objective-back>Retour aux objectifs</button></div>
          <div class="objective-editor-layout"><section class="panel"><form data-objective-editor>
          ${field("name","Nom de l'objectif",objective.name,{required:true,multiline:false})}
          ${field("description","Offre et objectif commercial",objective.description,{required:true})}
          ${field("target","Entreprises cibles",objective.target)}
          ${field("geography","Zone géographique",objective.geography,{multiline:false})}
          ${field("instructions","Consignes de l'agent",listValue(agent.instructions),{required:true})}
          ${field("context","Contexte durable",agent.context)}
          <details><summary>Critères, contacts et exemples</summary>
          ${field("positive_signals","Signaux recherchés — un par ligne",listValue(objective.positive_signals))}
          ${field("negative_signals","Exclusions — une par ligne",listValue(objective.negative_signals))}
          ${field("target_roles","Rôles à contacter — un par ligne",listValue(agent.target_roles))}
          ${field("questions","Questions à vérifier — une par ligne",listValue(objective.questions))}
          ${field("triggers","Déclencheurs de sélection — un par ligne",listValue(agent.triggers))}
          ${field("sourcing_guidance","Consignes de recherche",objective.sourcing_guidance)}
          ${field("approach_hint","Angle d'approche",objective.approach_hint)}
          <h3>Exemples de demandes</h3><div data-objective-examples></div><button class="button" type="button" data-add-example>Ajouter un exemple</button>
          ${field("additional_requirements","Exigences de restitution — une par ligne",listValue(agent.output_contract?.additional_requirements))}
          </details><div class="actions"><button class="button primary" type="submit">Enregistrer l'objectif</button></div><p class="form-feedback" data-editor-feedback role="status" aria-live="polite"></p></form></section>
          <section class="panel" id="objective-documents"><h3>Documents de l'objectif</h3><p class="hint">Documents repris lors des prochaines recherches, y compris planifiées.</p>
          <div class="objective-documents">${documents.length?documents.map(doc=>`<article class="evidence"><strong>${esc(doc.original_name||doc.name||"Document")}</strong><p class="meta">${esc(doc.mime_type||"")} · ${Math.round((doc.byte_size||0)/1024)} Ko · ${{complete:"Texte disponible",empty:"Aucun texte extrait",failed:"Extraction à vérifier"}[doc.extraction_status]||"À vérifier"}</p><details><summary>Provenance et empreinte</summary><p class="meta">${esc(doc.created_at||"")} · ${esc(doc.provenance?.source_type||"")}</p><p class="document-hash">${esc(doc.sha256||"")}</p><p class="meta">Contenu utilisé comme contexte non fiable, soumis aux consignes de l'objectif.</p>${doc.extraction_error?`<p class="form-feedback error">${esc(doc.extraction_error)}</p>`:""}</details></article>`).join(""):"<p class='meta'>Aucun document joint.</p>"}</div>
          <form data-document-upload><label for="objective-file">Ajouter un document</label><input id="objective-file" type="file" accept=".pdf,.docx,.txt,.md,.json,.csv,.html,.htm" required><p class="hint">PDF, Word, texte, Markdown, JSON, CSV ou HTML · 10 Mo maximum ici.</p><button class="button" type="submit">Joindre le document</button><p class="form-feedback" data-document-feedback role="status" aria-live="polite"></p></form>
          <h3>Notes enregistrées</h3>${notes.map(note=>`<details class="evidence"><summary>Note du ${esc(String(note.updated_at||note.created_at||"").slice(0,10))}</summary><p class="objective-note">${esc(note.text)}</p></details>`).join("")||"<p class='meta'>Aucune note.</p>"}
          <form data-objective-note>${field("note","Ajouter une note","")}<button class="button" type="submit">Enregistrer la note</button><p class="form-feedback" data-note-feedback role="status" aria-live="polite"></p></form></section></div>`;
        target.querySelector("[data-objective-back]").onclick=()=>renderObjectives(target);
        const examples=target.querySelector("[data-objective-examples]");
        function addExample(example={}) {
          const row=document.createElement("div");row.className="objective-example";
          row.innerHTML=`<label>Demande type<textarea data-example-request rows="2" required>${esc(example.request||"")}</textarea></label><label>Résultat attendu<textarea data-example-focus rows="2" required>${esc(example.expected_focus||"")}</textarea></label><button type="button" class="button" data-remove-example>Retirer l'exemple</button>`;
          row.querySelector("[data-remove-example]").onclick=()=>row.remove();examples.append(row);
        }
        (agent.examples||[]).forEach(addExample);
        target.querySelector("[data-add-example]").onclick=()=>addExample();
        async function refreshEditorContext() {
          const fresh=await callLeadTool("get_lead_objective",{objective_id:id});rememberObjective(fresh);
          const values=new FormData(target.querySelector("[data-objective-editor]"));
          const draft={...objective,documents:fresh.documents,notes:fresh.notes,agent:{...agent}};
          for(const key of ["name","description","target","geography","sourcing_guidance","approach_hint"])draft[key]=String(values.get(key)||"");
          for(const key of ["positive_signals","negative_signals","questions"])draft[key]=splitLines(values.get(key));
          for(const key of ["instructions","context"])draft.agent[key]=String(values.get(key)||"");
          for(const key of ["target_roles","triggers"])draft.agent[key]=splitLines(values.get(key));
          draft.agent.examples=[...examples.querySelectorAll(".objective-example")].map(row=>({request:row.querySelector("[data-example-request]").value,expected_focus:row.querySelector("[data-example-focus]").value}));
          draft.agent.output_contract={...(agent.output_contract||{}),additional_requirements:splitLines(values.get("additional_requirements"))};
          showObjectiveEditor(target,draft,true);
        }
        target.querySelector("[data-objective-editor]").onsubmit=async event=>{
          event.preventDefault();const form=event.currentTarget,feedback=form.querySelector("[data-editor-feedback]"),button=form.querySelector("[type=submit]");
          const values=new FormData(form),args={objective_id:id,expected_revision:objective.revision,expected_agent_revision:agent.revision};
          for(const key of ["name","description","target","geography","instructions","context","sourcing_guidance","approach_hint"])args[key]=String(values.get(key)||"").trim();
          for(const key of ["positive_signals","negative_signals","target_roles","questions","triggers"])args[key]=splitLines(values.get(key));
          args.examples=[...examples.querySelectorAll(".objective-example")].map(row=>({request:row.querySelector("[data-example-request]").value.trim(),expected_focus:row.querySelector("[data-example-focus]").value.trim()}));
          args.output_contract={...(agent.output_contract||{}),additional_requirements:splitLines(values.get("additional_requirements"))};
          button.disabled=true;feedback.classList.remove("error");feedback.textContent="Enregistrement…";
          try {
            if(!canCallLeadTool()) {await followUp(`Enregistre ces modifications explicites avec update_lead_objective, puis affiche render_lead_objectives. Paramètres : ${JSON.stringify(args)}`,false);feedback.textContent="Modifications transmises au chat pour enregistrement.";return;}
            objective=await callLeadTool("update_lead_objective",args);rememberObjective(objective);showObjectiveEditor(target,objective);
            target.querySelector("[data-editor-feedback]").textContent="Objectif enregistré. Les prochaines recherches utiliseront ces consignes.";
          } catch(error) {feedback.textContent=error.message;feedback.classList.add("error");} finally {button.disabled=false;}
        };
        target.querySelector("[data-document-upload]").onsubmit=async event=>{
          event.preventDefault();const form=event.currentTarget,feedback=form.querySelector("[data-document-feedback]"),button=form.querySelector("button"),file=form.querySelector("input").files?.[0];
          if(!file)return;
          if(file.size>10*1024*1024){feedback.textContent="Ce document dépasse 10 Mo. Joignez-le dans le chat pour l'ajouter.";feedback.classList.add("error");return;}
          button.disabled=true;feedback.classList.remove("error");feedback.textContent="Ajout et lecture du document…";
          try {
            if(!canCallLeadTool())throw new Error("L'ajout direct est indisponible dans cet hôte. Joignez le fichier dans le chat en indiquant cet objectif.");
            const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=()=>reject(new Error("Lecture du fichier impossible."));reader.readAsDataURL(file);});
            const doc=await callLeadTool("upload_lead_objective_document",{objective_id:id,filename:file.name,content_base64:encoded});
            await refreshEditorContext();target.querySelector("[data-document-feedback]").textContent=doc.extraction_status==="complete"?"Document ajouté et disponible pour l'agent.":"Document ajouté. Son texte nécessite une vérification.";
          }catch(error){feedback.textContent=error.message;feedback.classList.add("error");}finally{button.disabled=false;}
        };
        target.querySelector("[data-objective-note]").onsubmit=async event=>{
          event.preventDefault();const form=event.currentTarget,text=form.querySelector("textarea").value.trim(),feedback=form.querySelector("[data-note-feedback]"),button=form.querySelector("button");if(!text)return;
          button.disabled=true;feedback.textContent="Enregistrement…";
          try {
            if(!canCallLeadTool()){await followUp(`Ajoute cette note à l'objectif ${id} avec add_lead_objective_note : ${JSON.stringify(text)}. Réaffiche ensuite render_lead_objectives.`,false);feedback.textContent="Note transmise au chat pour enregistrement.";return;}
            await callLeadTool("add_lead_objective_note",{objective_id:id,text});await refreshEditorContext();target.querySelector("[data-note-feedback]").textContent="Note enregistrée.";
          }catch(error){feedback.textContent=error.message;feedback.classList.add("error");}finally{button.disabled=false;}
        };
        if(focusDocuments)target.querySelector("#objective-documents").scrollIntoView({block:"nearest"});
      }
      async function deleteObjective(id,button) {
        const objective=objectives().find(row=>(row.objective_id||row.id)===id);
        if(!objective)return;
        const name=objective.name||objective.objective_name||id;
        const feedback=button.closest(".objective-card")?.querySelector("[data-objective-feedback]");
        if(button.dataset.confirmDelete!=="true") {
          button.dataset.confirmDelete="true";
          button.dataset.deleteLabel=button.textContent;
          button.textContent="Confirmer";
          const cancel=document.createElement("button");
          cancel.type="button";cancel.className="button";cancel.dataset.cancelDelete=id;cancel.textContent="Annuler";
          cancel.onclick=()=>{button.dataset.confirmDelete="false";button.textContent=button.dataset.deleteLabel||"Supprimer";cancel.remove();if(feedback)feedback.textContent="";};
          button.after(cancel);
          if(feedback)feedback.textContent=`Confirmez pour retirer « ${name} » des listes actives. Ses consignes, documents et historique resteront archivés et récupérables.`;
          return;
        }
        button.parentElement?.querySelector(`[data-cancel-delete="${CSS.escape(id)}"]`)?.remove();
        button.disabled=true;
        if(feedback){feedback.classList.remove("error");feedback.textContent="Suppression…";}
        try {
          if(!canCallLeadTool()) {
            await followUp(`Archive l'objectif ${id} avec archive_lead_objective, puis affiche render_lead_objectives.`,false);
            if(feedback)feedback.textContent="Suppression transmise au chat pour confirmation.";
            return;
          }
          const archived=await callLeadTool("archive_lead_objective",{objective_id:id,archived:true});
          if(archived.status!=="archived")throw new Error("L'objectif n'a pas pu être archivé.");
          data.objectives=objectives().filter(row=>(row.objective_id||row.id)!==id);
          if(data.active_objective_id===id)data.active_objective_id=null;
          renderObjectives(document.getElementById("view"));
        } catch(error) {
          button.disabled=false;button.dataset.confirmDelete="false";button.textContent=button.dataset.deleteLabel||"Supprimer";
          if(feedback){feedback.textContent=error.message;feedback.classList.add("error");}
        }
      }
      function attachObjectiveDocument(id) { return editObjective(id,true); }
      function renderScheduleSettings(target) {
        const rows=objectives();
        target.innerHTML=`<h3>Planification par objectif</h3><p class="hint">Choisissez l'objectif, les jours, l'heure locale et le nombre de nouveaux prospects. Chaque exécution reprend ses consignes et documents enregistrés.</p>${rows.length?`<label for="schedule-objective">Objectif à planifier</label><select id="schedule-objective">${rows.map(row=>`<option value="${esc(row.objective_id)}">${esc(row.name)}</option>`).join("")}</select><div data-schedule-form></div>`:"<p class='meta'>Créez un objectif dans l'onglet Objectifs pour le planifier.</p>"}`;
        if(!rows.length)return;
        const select=target.querySelector("select");if(rows.some(row=>row.objective_id===data.active_objective_id))select.value=data.active_objective_id;
        const draw=()=>drawScheduleForm(target.querySelector("[data-schedule-form]"),objectives().find(row=>row.objective_id===select.value));
        select.onchange=draw;draw();
      }
      function drawScheduleForm(target,objective) {
        const schedule=objective.schedule||{},settings=schedule.settings||{},days=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"];
        target.innerHTML=`<p><span data-schedule-status class="chip ${schedule.sync_status==="active"?"brand":""}">${esc(scheduleLabels[schedule.sync_status]||scheduleLabels.not_configured)}</span></p>
          ${schedule.confirmed_at?`<p class="hint">Dernière confirmation Codex : ${esc(new Date(schedule.confirmed_at).toLocaleString("fr-FR"))}</p>`:""}
          <form data-objective-schedule><label class="checkbox-label"><input name="enabled" type="checkbox" ${settings.enabled?"checked":""}> Générer automatiquement des prospects</label>
          <div class="schedule-grid"><div><label for="schedule-frequency">Fréquence</label><select id="schedule-frequency" name="frequency"><option value="daily">Tous les jours</option><option value="weekdays">Du lundi au vendredi</option><option value="weekly">Certains jours</option></select></div>
          <div><label for="schedule-time">Heure locale</label><input id="schedule-time" name="local_time" type="time" value="${esc(settings.local_time||"09:00")}" required></div>
          <div><label for="schedule-timezone">Fuseau horaire</label><input id="schedule-timezone" name="timezone" type="text" value="${esc(settings.timezone||"Europe/Paris")}" required></div>
          <div><label for="schedule-count">Prospects par exécution</label><input id="schedule-count" name="lead_count" type="number" min="1" max="25" value="${settings.lead_count||10}" required></div></div>
          <fieldset data-schedule-weekdays><legend>Jours de recherche</legend><div class="weekdays">${days.map((day,index)=>`<label class="checkbox-label"><input type="checkbox" name="weekdays" value="${index+1}" ${(settings.weekdays||[1]).includes(index+1)?"checked":""}>${day}</label>`).join("")}</div></fieldset>
          <p class="hint">Le Mac et Codex doivent être ouverts à l'heure prévue. La nouvelle liste revient dans la conversation de planification.</p>
          <div class="actions"><button class="button primary" type="submit">Enregistrer la planification</button></div><p class="form-feedback" data-schedule-feedback role="status" aria-live="polite"></p></form>`;
        const form=target.querySelector("form"),frequency=form.querySelector("[name=frequency]");frequency.value=settings.frequency||"daily";
        const toggleDays=()=>{form.querySelector("fieldset").hidden=frequency.value!=="weekly";};frequency.onchange=toggleDays;toggleDays();
        if(schedule.host_editable===false) {
          form.querySelectorAll("input,select,button").forEach(control=>control.disabled=true);
          form.querySelector("[data-schedule-feedback]").textContent="Planification gérée dans Codex, en lecture seule ici. Aucune automatisation Claude n’a été créée. Ouvrez Codex pour la modifier.";
          return;
        }
        form.onsubmit=async event=>{
          event.preventDefault();const values=new FormData(form),feedback=form.querySelector("[data-schedule-feedback]"),button=form.querySelector("[type=submit]");
          const settings={enabled:values.has("enabled"),frequency:String(values.get("frequency")),local_time:String(values.get("local_time")),timezone:String(values.get("timezone")).trim(),lead_count:Number(values.get("lead_count")),weekdays:values.getAll("weekdays").map(Number)};
          if(!settings.weekdays.length&&settings.frequency==="weekly"){feedback.textContent="Choisissez au moins un jour.";feedback.classList.add("error");return;}
          if(!settings.weekdays.length)settings.weekdays=[1];
          const args={objective_id:objective.objective_id,settings,expected_revision:schedule.revision||0};
          button.disabled=true;feedback.classList.remove("error");feedback.textContent="Enregistrement…";
          try {
            if(!canCallLeadTool()){await followUp(`Enregistre cette planification avec save_lead_objective_schedule : ${JSON.stringify(args)}. Exécute ensuite le handoff avec automation_update, confirme sa liaison après succès et affiche render_lead_objectives dans Réglages.`,false);feedback.textContent="Planification transmise au chat pour enregistrement et activation.";return;}
            const result=await callLeadTool("save_lead_objective_schedule",args);objective.schedule=result.schedule;schedule.revision=result.schedule.revision;
            target.querySelector("[data-schedule-status]").textContent=scheduleLabels[result.schedule.sync_status]||scheduleLabels.pending;
            if(result.next_action==="configure_host_automation"){
              feedback.textContent="Réglages enregistrés. Synchronisation avec Codex demandée…";
              await followUp(`Synchronise la planification enregistrée de l'objectif ${objective.objective_id}. Charge get_lead_objective_schedule, puis exécute son handoff avec l'outil automation_update de Codex, en réutilisant l'automatisation existante. Après succès, appelle confirm_lead_objective_schedule avec l'identifiant réel, la révision et le statut retournés. Affiche render_lead_objectives dans Réglages.`,false);
            }else{drawScheduleForm(target,objective);target.querySelector("[data-schedule-feedback]").textContent="Réglages enregistrés.";}
          }catch(error){feedback.textContent=error.message;feedback.classList.add("error");}finally{button.disabled=false;}
        };
      }
"""
