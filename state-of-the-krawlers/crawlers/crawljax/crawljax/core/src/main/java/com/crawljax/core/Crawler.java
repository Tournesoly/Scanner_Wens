package com.crawljax.core;

import com.crawljax.browser.EmbeddedBrowser;
import com.crawljax.condition.browserwaiter.WaitConditionChecker;
import com.crawljax.core.configuration.CrawlRules;
import com.crawljax.core.configuration.CrawlRules.CrawlPriorityMode;
import com.crawljax.core.configuration.CrawljaxConfiguration;
import com.crawljax.core.plugin.Plugins;
import com.crawljax.core.state.*;
import com.crawljax.core.state.Eventable.EventType;
import com.crawljax.di.CoreModule.CandidateElementExtractorFactory;
import com.crawljax.di.CoreModule.FormHandlerFactory;
import com.crawljax.di.CoreModule.TrainingFormHandlerFactory;
import com.crawljax.forms.FormHandler;
import com.crawljax.forms.FormInput;
import com.crawljax.oraclecomparator.StateComparator;
import com.crawljax.util.ElementResolver;
import com.crawljax.util.UrlUtils;
import com.google.common.base.Preconditions;
import com.google.common.collect.ImmutableList;
import org.openqa.selenium.ElementNotInteractableException;
import org.openqa.selenium.NoSuchElementException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.inject.Inject;
import javax.inject.Provider;
import java.io.File;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Map.Entry;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Crawler {

	private static final Logger LOG = LoggerFactory.getLogger(Crawler.class);

	private final AtomicInteger crawlDepth = new AtomicInteger();
	private final int maxDepth;
	private final EmbeddedBrowser browser;
	private final CrawlerContext context;
	private final StateComparator stateComparator;
	private final URI url;
	private final URI basicAuthUrl;
	private final Plugins plugins;
	private final FormHandler formHandler;
	private final CrawlRules crawlRules;
	private final WaitConditionChecker waitConditionChecker;
	private final CandidateElementExtractor candidateExtractor;
	private final UnfiredCandidateActions candidateActionCache;
	private final Provider<InMemoryStateFlowGraph> graphProvider;
	private final StateVertexFactory vertexFactory;
	public static File outputDir;

	private CrawlPath crawlpath;
	private StateMachine stateMachine;

	@Inject Crawler(CrawlerContext context, CrawljaxConfiguration config,
			StateComparator stateComparator,
			UnfiredCandidateActions candidateActionCache, FormHandlerFactory formHandlerFactory,
			TrainingFormHandlerFactory trainingFormHandlerFactory,
			WaitConditionChecker waitConditionChecker,
			CandidateElementExtractorFactory elementExtractor,
			Provider<InMemoryStateFlowGraph> graphProvider, Plugins plugins,
			StateVertexFactory vertexFactory) {
		this.context = context;
		this.graphProvider = graphProvider;
		this.vertexFactory = vertexFactory;
		this.browser = context.getBrowser();
		this.url = config.getUrl();
		this.basicAuthUrl = config.getBasicAuthUrl();
		this.plugins = plugins;
		this.crawlRules = config.getCrawlRules();
		this.maxDepth = config.getMaximumDepth();
		this.stateComparator = stateComparator;
		this.candidateActionCache = candidateActionCache;
		this.waitConditionChecker = waitConditionChecker;
		this.candidateExtractor = elementExtractor.newExtractor(browser);
		outputDir = config.getOutputDir();

		switch (crawlRules.getFormFillMode()) {
			case RANDOM:
				// RANDOM TRUE
				this.formHandler = formHandlerFactory.newFormHandler(browser);
				break;
			case XPATH_TRAINING:
			case TRAINING:
				this.formHandler = trainingFormHandlerFactory.newTrainingFormHandler(browser);
				break;
			default:
				this.formHandler = formHandlerFactory.newFormHandler(browser);
				break;
		}
	}

	/**
	 * Close the browser.
	 */
	public void close() {
		browser.close();
	}

	/**
	 * Reset the crawler to its initial state.
	 */
	public void reset() {
		CrawlSession session = context.getSession();
		if (crawlpath != null) {
			session.addCrawlPath(crawlpath);
		}
		List<StateVertex> onURLSetTemp = new ArrayList<>();
		if (stateMachine != null)
			onURLSetTemp = stateMachine.getOnURLSet();
		stateMachine = new StateMachine(graphProvider.get(), crawlRules.getInvariants(), plugins,
				stateComparator, onURLSetTemp);
		context.setStateMachine(stateMachine);
		crawlpath = new CrawlPath();
		context.setCrawlPath(crawlpath);
		browser.handlePopups();
		browser.goToUrl(url);
		// Checks the landing page for URL and sets the current page accordingly
		checkOnURLState();
		plugins.runOnUrlLoadPlugins(context);
		crawlDepth.set(0);
	}

	private void checkOnURLState() {
		StateVertex newState = stateMachine.newStateFor(browser);
		StateVertex clone = stateMachine.getStateFlowGraph().putIfAbsent(newState);
		if (clone == null) {
			stateMachine.setCurrentState(newState);
			stateMachine.runOnInvariantViolationPlugins(context);

			plugins.runOnNewStatePlugins(context, newState);

			parseCurrentPageForCandidateElements();
			stateMachine.getOnURLSet().add(newState);
		} else {
			if (!clone.getName().equalsIgnoreCase("index")) {
				LOG.info("index has changed to: {}", clone.getName());
				if (!stateMachine.getOnURLSet().contains(clone))
					stateMachine.getOnURLSet().add(clone);
			}
			stateMachine.setCurrentState(clone);
		}
	}

	/**
	 * @param crawlTask The {@link StateVertex} this {@link Crawler} should visit to crawl.
	 */
	public void execute(StateVertex crawlTask) {
		LOG.debug("Resetting the crawler and going to state {}", crawlTask.getName());
		reset();

		try {
			// follow(CrawlPath.copyOf(eventables), crawlTask);
			boolean reachable = reachFromHome(crawlTask);
			if (!reachable) {
				LOG.info("state unreachable: Removing from candidate actions {}",
						crawlTask.getName());
				candidateActionCache.purgeActionsForState(crawlTask);
				crawlpath = null; // don't insert duplicate crawlpaths
				return;
			}
			crawlThroughActions();
		} catch (StateUnreachableException ex) {
			LOG.info(ex.getMessage());
			LOG.debug(ex.getMessage(), ex);
			candidateActionCache.purgeActionsForState(ex.getTarget());
			crawlpath = null; // don't insert duplicate crawlpaths
		} catch (CrawlerLeftDomainException e) {
			LOG.info("The crawler left the domain. No biggy, we'll just go somewhere else.");
			LOG.debug("Domain escape was {}", e.getMessage());
		}
	}

	private boolean reachFromHome(StateVertex crawlTask) {
		// TODO: Changes to Eventables need to be accounted for

		StateVertex currentOnURLState = stateMachine.getCurrentState();
		ImmutableList<Eventable> path = null;
		try {
			path = shortestPathTo(crawlTask);
		} catch (Exception Ex) {
			LOG.info(crawlTask.getName() + " no path from "
					+ stateMachine.getCurrentState().getName());
			path = null;
		}
		if (path != null) {
			try {
				follow(CrawlPath.copyOf(path), crawlTask);
				return true;
			} catch (Exception Ex) {
				LOG.info("Not a valid path anymore" + stateMachine.getCurrentState().getName()
						+ " : " + crawlTask.getName());
				crawlpath = null;
				reset();
			}
		}

		for (int i = 0; i < stateMachine.getOnURLSet().size(); i++) {
			StateVertex onURL = stateMachine.getOnURLSet().get(i);
			stateMachine.setCurrentState(onURL);
			path = null;
			try {
				path = shortestPathTo(crawlTask, onURL);
			} catch (Exception Ex) {
				Ex.printStackTrace();
				LOG.info("{} no path from {}", crawlTask.getName(), onURL.getName());
				path = null;
			}
			if (path != null) {
				try {
					follow(CrawlPath.copyOf(path), crawlTask);
					/*
					 * Add edge from the current onURL page and the first state in the crawlpath
					 * that worked
					 */
					Eventable newEvent = (Eventable) path.get(0).clone();
					// new Eventable(path.get(0).getElement(), path.get(0).getEventType());
					newEvent.setSource(currentOnURLState);
					newEvent.setTarget(path.get(0).getTargetStateVertex());

					stateMachine.getStateFlowGraph().addEdge(currentOnURLState,
							path.get(0).getTargetStateVertex(), newEvent);

					// Fix the crawlpath with newly added edge
					crawlpath.remove(0);
					crawlpath.set(0, newEvent);
					return true;
				} catch (Exception Ex) {
					LOG.info("Not a valid path anymore" + onURL.getName() + " : "
							+ crawlTask.getName());
					crawlpath = null;
					reset();
				}
			}
		}
		return false;
	}

	private ImmutableList<Eventable> shortestPathTo(StateVertex crawlTask, StateVertex onURL) {
		StateFlowGraph graph = context.getSession().getStateFlowGraph();
		return graph.getShortestPath(onURL, crawlTask);
	}

	private ImmutableList<Eventable> shortestPathTo(StateVertex crawlTask) {
		StateFlowGraph graph = context.getSession().getStateFlowGraph();
		StateVertex currState = null;
		if (stateMachine != null)
			currState = stateMachine.getCurrentState();

		if (currState != null && currState != graph.getInitialState()) {
			LOG.info(
					"Initial state not the same as current state : Getting shortest path from current state");
			return graph.getShortestPath(currState, crawlTask);
		}
		return graph.getShortestPath(graph.getInitialState(), crawlTask);
	}

	private void follow(CrawlPath path, StateVertex targetState)
			throws CrawljaxException {
		StateVertex currState = null;
		if (stateMachine != null) {
			currState = stateMachine.getCurrentState();
		}
		if (currState == null) {
			currState = context.getSession().getInitialState();
		}
		for (Eventable clickable : path) {
			checkCrawlConditions(targetState);
			LOG.debug("Backtracking by executing {} on element: {}", clickable.getEventType(),
					clickable);
			currState = changeState(targetState, clickable);
			handleInputElements(clickable);
			tryToFireEvent(targetState, currState, clickable);
			checkCrawlConditions(targetState);
		}

		// This condition is probably unnecessary.
		if (!currState.equals(targetState)) {
			throw new StateUnreachableException(targetState,
					"The path didn't result in the desired state but in state "
							+ currState.getName());
		}
	}

	private void checkCrawlConditions(StateVertex targetState) {
		if (!candidateExtractor.checkCrawlCondition()) {
			throw new StateUnreachableException(targetState,
					"Crawl conditions not complete. Not following path");
		}
	}

	private StateVertex changeState(StateVertex targetState, Eventable clickable) {
		boolean switched = stateMachine.changeState(clickable.getTargetStateVertex());
		if (!switched) {
			throw new StateUnreachableException(targetState, "Could not switch states");
		}
		StateVertex curState = clickable.getTargetStateVertex();
		crawlpath.add(clickable);
		return curState;
	}

	private void tryToFireEvent(StateVertex targetState, StateVertex curState,
			Eventable clickable) {
		browser.handlePopups();
		if (fireEvent(clickable)) {
			if (crawlerLeftDomain()) {
				throw new StateUnreachableException(targetState,
						"Domain left while following path");
			}
			int depth = crawlDepth.incrementAndGet();
			LOG.info("Crawl depth is now {}", depth);
			plugins.runOnRevisitStatePlugins(context, curState);

		} else {
			throw new StateUnreachableException(targetState,
					"couldn't fire eventable " + clickable);
		}
	}

	/**
	 * Enters the form data. First, the related input elements (if any) to the eventable are filled
	 * in and then it tries to fill in the remaining input elements.
	 *
	 * @param eventable the eventable element.
	 */
	private void handleInputElements(Eventable eventable) {
		CopyOnWriteArrayList<FormInput> formInputs = eventable.getRelatedFormInputs();

		for (FormInput formInput : formHandler.getFormInputs()) {
			if (!formInputs.contains(formInput)) {
				formInputs.add(formInput);
			}
		}

		formHandler.handleFormElements(formInputs);

	}

	/**
	 * Try to fire a given event on the Browser.
	 *
	 * @param eventable the eventable to fire
	 * @return true iff the event is fired
	 */
	private boolean fireEvent(Eventable eventable) {
		Eventable eventToFire = eventable;
		if (eventable.getIdentification().getHow().toString().equals("xpath")
				&& eventable.getRelatedFrame().equals("")) {
			eventToFire = resolveByXpath(eventable, eventToFire);
		}
		boolean isFired = false;
		try {
			isFired = browser.fireEventAndWait(eventToFire);
			
		} catch (ElementNotInteractableException | NoSuchElementException e) {
			// Handle hidden anchor tags
			if (crawlRules.isCrawlHiddenAnchors() && eventToFire.getElement() != null
					&& "A".equals(eventToFire.getElement().getTag())) {
				isFired = visitAnchorHrefIfPossible(eventToFire);
			} else {
				LOG.debug("Ignoring invisible element {}", eventToFire.getElement());
			}
			
		} catch (InterruptedException e) {
			LOG.debug("Interrupted during fire event");
			interruptThread();
			return false;
		}

		LOG.debug("Event fired={} for eventable {}", isFired, eventable);

		if (isFired) {
			// Let the controller execute its specified wait operation on the browser thread safe.
			waitConditionChecker.wait(browser);
			browser.closeOtherWindows();
			return true;
		} else {
			/*
			 * Execute the OnFireEventFailedPlugins with the current crawlPath with the crawlPath
			 * removed 1 state to represent the path TO here.
			 */
			plugins.runOnFireEventFailedPlugins(context, eventable,
					crawlpath.immutableCopyWithoutLast());
			return false; // no event fired
		}
	}

	private Eventable resolveByXpath(Eventable eventable, Eventable eventToFire) {
		// The path in the page to the 'clickable' (link, div, span, etc)
		String xpath = eventable.getIdentification().getValue();

		// The type of event to execute on the 'clickable' like onClick,
		// mouseOver, hover, etc
		EventType eventType = eventable.getEventType();

		// Try to find a 'better' / 'quicker' xpath
		String newXPath = new ElementResolver(eventable, browser).resolve();
		if (newXPath != null && !xpath.equals(newXPath)) {
			LOG.debug("XPath changed from {} to {} relatedFrame: {}", xpath, newXPath,
					eventable.getRelatedFrame());
			eventToFire = new Eventable(new Identification(Identification.How.xpath, newXPath),
					eventType);
		}
		return eventToFire;
	}

	private boolean visitAnchorHrefIfPossible(Eventable eventable) {
		Element element = eventable.getElement();
		String href = element.getAttributeOrNull("href");
		if (href == null) {
			LOG.info("Anchor {} has no href and is invisible so it will be ignored", element);
		} else {
			LOG.info("Found an invisible link with href={}", href);
			URI url = UrlUtils.extractNewUrl(browser.getCurrentUrl(), href);
			browser.goToUrl(url);
			return true;
		}
		return false;
	}

	/**
	 * Crawl through the actions of the current state. The browser keeps firing
	 * {@link CandidateCrawlAction}s stored in the state until the DOM changes. When it does, it
	 * checks if the new dom is a clone or a new state. In continues crawling in that new or clone
	 * state. If the browser leaves the current domain, the crawler tries to get back to the
	 * previous state.
	 * <p>
	 * The methods stops when {@link Thread#interrupted()}
	 */
	private void crawlThroughActions() {
		boolean interrupted = Thread.interrupted();
		CandidateCrawlAction action =
				candidateActionCache.pollActionOrNull(stateMachine.getCurrentState());
		while (action != null && !interrupted) {
			boolean newStateFound = false;
			CandidateElement element = action.getCandidateElement();
			if (element.allConditionsSatisfied(browser)) {
				Eventable event = new Eventable(element, action.getEventType());
				handleInputElements(event);
				waitForRefreshTagIfAny(event);

				boolean fired = fireEvent(event);
				if (fired) {
					newStateFound = inspectNewState(event);
				}
			} else {
				LOG.info(
						"Element {} not clicked because not all crawl conditions were satisfied",
						element);
			}

			if (newStateFound && stateMachine.getCurrentState().hasNearDuplicate()) {
				action = null;
			} else {
				// We have to check if we are still in the same state.
				action = candidateActionCache.pollActionOrNull(stateMachine.getCurrentState());
			}
			interrupted = Thread.interrupted();
			if (!interrupted && crawlerLeftDomain()) {
				/*
				 * It's okay to have left the domain because the action didn't complete due to an
				 * interruption.
				 */
				throw new CrawlerLeftDomainException(browser.getCurrentUrl());
			}
			if (this.crawlRules.getCrawlPriorityMode() == CrawlPriorityMode.RANDOM_GLOBAL) {
				break;
			}
		}
		if (interrupted) {
			LOG.info(
					"Interrupted while firing actions. Putting back the actions on the todo list");
			if (action != null) {
				candidateActionCache.addActions(ImmutableList.of(action),
						stateMachine.getCurrentState());
			}
			interruptThread();
		}
	}

	private void interruptThread() {
		if (crawlpath != null) {
			context.getSession().addCrawlPath(crawlpath);
		}
		Thread.currentThread().interrupt();
	}

	private boolean inspectNewState(Eventable event) {
		browser.handlePopups();
		if (crawlerLeftDomain()) {
			LOG.debug("The browser left the domain. Going back one state...");
			goBackOneState();
			return false;
		} else {
			StateVertex newState = stateMachine.newStateFor(browser);
			if (domChanged(event, newState)) {
				return inspectNewDom(event, newState);
			} else {
				LOG.debug("Dom unchanged");
				return false;
			}
		}
	}

	private boolean domChanged(final Eventable eventable, StateVertex newState) {
		//  DOM comparison behavior of StateVertex
		StateVertex stateBefore = stateMachine.getCurrentState();
		boolean isChanged = !newState.equals(stateBefore);

		if (isChanged) {
			LOG.debug("State is Changed!");
			return true;
		}

		LOG.debug("State not Changed!");
		return false;
	}

	private boolean inspectNewDom(Eventable event, StateVertex newState) {
		LOG.debug("The DOM has changed. Event added to the crawl path");
		crawlpath.add(event);
		boolean isNewState = stateMachine.switchToStateAndCheckIfClone(event, newState, context);
		if (isNewState) {
			int depth = crawlDepth.incrementAndGet();
			LOG.info("New DOM is a new state! crawl depth is now {}", depth);
			if (maxDepth == depth) {
				LOG.debug("Maximum depth achieved. Not crawling this state any further");
				return true;
			} else {
				parseCurrentPageForCandidateElements();
				return true;
			}
		} else {
			if (event.getId() == -1) {
				// Removing the clone Edge and adding the SFG edge to the crawlpath
				crawlpath.remove(crawlpath.size() - 1);
				for (Eventable edge : stateMachine.getStateFlowGraph().getAllEdges()) {
					if (edge.equals(event)) {
						crawlpath.add(edge);
						LOG.debug(
								"CrawlPath fixed !! The eventable fired was a clone of existing edge");
						break;
					}
				}
			}
			LOG.debug("New DOM is a clone state. Continuing in that state.");
			return false;
		}
	}

	private void parseCurrentPageForCandidateElements() {
		StateVertex currentState = stateMachine.getCurrentState();
		LOG.debug("Parsing DOM of state {} for candidate elements", currentState.getName());
		ImmutableList<CandidateElement> extract = candidateExtractor.extract(currentState);

		plugins.runPreStateCrawlingPlugins(context, extract, currentState);
		candidateActionCache.addActions(extract, currentState);
	}

	private void waitForRefreshTagIfAny(final Eventable eventable) {
		if ("meta".equalsIgnoreCase(eventable.getElement().getTag())) {
			Pattern p = Pattern.compile("(\\d+);\\s+URL=(.*)");
			for (Entry<String, String> e : eventable.getElement().getAttributes().entrySet()) {
				Matcher m = p.matcher(e.getValue());
				long waitTime = parseWaitTimeOrReturnDefault(m);
				try {
					Thread.sleep(waitTime);
				} catch (InterruptedException ex) {
					LOG.info("Crawler timed out while waiting for page to reload");
					interruptThread();
				}
			}
		}
	}

	private boolean crawlerLeftDomain() {
		return !UrlUtils.isSameDomain(browser.getCurrentUrl(), url);
	}

	private long parseWaitTimeOrReturnDefault(Matcher m) {
		long waitTime = TimeUnit.SECONDS.toMillis(10);
		if (m.find()) {
			LOG.debug("URL: {}", m.group(2));
			try {
				waitTime = Integer.parseInt(m.group(1)) * 1000;
			} catch (NumberFormatException ex) {
				LOG.info(
						"Could parse the amount of time to wait for a META tag refresh. Waiting 10 seconds...");
			}
		}
		return waitTime;
	}

	private void goBackOneState() {
		LOG.debug("Going back one state");
		CrawlPath currentPath = crawlpath.immutableCopy();
		crawlpath = null;
		StateVertex current = stateMachine.getCurrentState();
		reset();
		// Could change landing page here. Tests fail because of this. 
		CrawlPath shortestPath = new CrawlPath(shortestPathTo(current));
		if (!currentPath.get(0).getSourceStateVertex()
				.equals(shortestPath.get(0).getSourceStateVertex())) {
			LOG.info(
					"Landing Page has changed on reset trying to go back one page!! Saving that path");
			CrawlSession session = context.getSession();
			session.addCrawlPath(currentPath);
		}
		currentPath = shortestPath;
		follow(currentPath, current);
	}

	/**
	 * This method calls the index state. It should be called once per crawl in order to setup the
	 * crawl.
	 *
	 * @return The initial state.
	 */
	public StateVertex crawlIndex() {
		LOG.debug("Setting up vertex of the index page");

		if (basicAuthUrl != null) {
			browser.goToUrl(basicAuthUrl);
		}

		browser.goToUrl(url);

		// Run url first load plugin to clear the application state
		plugins.runOnUrlFirstLoadPlugins(context);

		plugins.runOnUrlLoadPlugins(context);
		StateVertex index = vertexFactory.createIndex(url.toString(), browser.getStrippedDom(),
				stateComparator.getStrippedDom(browser), browser);
		Preconditions.checkArgument(index.getId() == StateVertex.INDEX_ID,
				"It seems some the index state is crawled more than once.");

		LOG.debug("Parsing the index for candidate elements");
		ImmutableList<CandidateElement> extract = candidateExtractor.extract(index);

		plugins.runPreStateCrawlingPlugins(context, extract, index);

		candidateActionCache.addActions(extract, index);

		return index;

	}

	public CrawlerContext getContext() {
		return context;
	}

	public CrawlRules getCrawlRules() {
		return crawlRules;
	}

}
